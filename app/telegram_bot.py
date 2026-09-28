"""Capa Visual y de Entrega: Cliente Interactivo del Bot de Telegram.

Responsabilidades:
- Enviar tarjetas PNG generadas (temp_card.png y temp_chart.png) a Telegram.
- Renderizar panel interactivo Inline Keyboard con los 4 botones requeridos:
    1. "⭐ Guardar en favoritos"  (SAVE_TREND)
    2. "📁 Ver favoritos"         (VIEW_FAVS o comando /favoritos)
    3. "📈 Gráfica de tendencias" (GET_CHART)
    4. "Consultar fuente"        (URL externa directa a la fuente pública)
- Escuchar y procesar interacciones en tiempo real mediante Long Polling asíncrono y Webhook.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging
import asyncio
import json
import os
import httpx
from dotenv import load_dotenv

from app.config import settings
from app.database import (
    mark_as_favorite,
    get_favorites,
    get_trend_by_id,
    get_recent_sent_trends,
)
from app.visual_engine import create_chart_png_card

logger = logging.getLogger("app.telegram_bot")

_polling_active = False
_polling_task: Optional[asyncio.Task] = None


def _get_credentials() -> tuple[str, str]:
    """Carga y retorna (bot_token, chat_id) desde las variables de entorno."""
    load_dotenv(settings.BASE_DIR / ".env", override=True)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.TELEGRAM_BOT_TOKEN
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or settings.TELEGRAM_CHAT_ID
    return bot_token, chat_id


def build_interactive_keyboard(
    trend_id: Optional[int] = None,
    source_url: Optional[str] = None
) -> Dict[str, Any]:
    """Genera la estructura del panel interactivo con las 4 opciones solicitadas:
    1. ⭐ Guardar en favoritos (callback_data: SAVE_TREND)
    2. 📁 Ver favoritos (callback_data: VIEW_FAVS)
    3. 📈 Gráfica de tendencias (callback_data: GET_CHART)
    4. 🔍 Profundizar datos (callback_data: DEEP_DIVE)
    """
    id_suffix = f":{trend_id}" if trend_id is not None else ""

    return {
        "inline_keyboard": [
            [
                {"text": "⭐ Guardar en favoritos", "callback_data": f"SAVE_TREND{id_suffix}"},
                {"text": "📁 Ver favoritos", "callback_data": "VIEW_FAVS"}
            ],
            [
                {"text": "📈 Gráfica de tendencias", "callback_data": f"GET_CHART{id_suffix}"},
                {"text": "🔍 Profundizar datos", "callback_data": f"DEEP_DIVE{id_suffix}"}
            ]
        ]
    }



async def answer_callback_query(
    callback_query_id: str,
    text: Optional[str] = None,
    show_alert: bool = False
) -> bool:
    """Envía la confirmación obligatoria a Telegram para desactivar el indicador de carga del botón."""
    bot_token, _ = _get_credentials()
    if not bot_token or not callback_query_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery"
    payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Error respondiendo callback_query: {e}")
        return False


async def send_telegram_message(
    text: str,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = "HTML",
    reply_markup: Optional[Dict[str, Any]] = None,
    reply_to_message_id: Optional[int] = None
) -> Dict[str, Any]:
    """Envía un mensaje de texto formateado a Telegram."""
    bot_token, default_chat = _get_credentials()
    target_chat = chat_id or default_chat

    if not bot_token or not target_chat:
        return {"success": False, "error": "MISSING_CREDENTIALS"}

    if len(text) > 4000:
        chunks = [text[i:i+3800] for i in range(0, len(text), 3800)]
        last_res = {"success": False}
        for chunk in chunks:
            last_res = await send_telegram_message(
                text=chunk,
                chat_id=chat_id,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id
            )
        return last_res

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload: Dict[str, Any] = {
        "chat_id": target_chat,
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, json=payload)
            res_json = resp.json()
            if resp.status_code == 200 and res_json.get("ok"):
                return {"success": True, "result": res_json}

            # Fallback en texto plano si falla el parseo de HTML
            if "can't parse entities" in str(res_json.get("description", "")):
                import re
                plain_text = re.sub(r"<[^>]+>", "", text)
                payload["text"] = plain_text
                payload.pop("parse_mode", None)
                retry_resp = await client.post(url, json=payload)
                return {"success": retry_resp.status_code == 200, "result": retry_resp.json()}

            return {"success": False, "error": res_json}
    except Exception as e:
        logger.error(f"Error enviando mensaje a Telegram: {e}")
        return {"success": False, "error": str(e)}


async def send_telegram_notification(
    photo_path: Optional[Path | str] = None,
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = "HTML",
    reply_to_message_id: Optional[int] = None
) -> Dict[str, Any]:
    """Envía una imagen (tarjeta PNG) a Telegram con el panel interactivo de 4 botones."""
    bot_token, default_chat = _get_credentials()
    target_chat = chat_id or default_chat

    if photo_path is None:
        target_photo = settings.BASE_DIR / "temp_card.png"
    else:
        target_photo = Path(photo_path)

    if not target_photo.exists():
        raise FileNotFoundError(f"Imagen no encontrada para envío: {target_photo}")

    final_caption = caption if caption is not None else ""

    if not bot_token or not target_chat:
        msg = "⚠️ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados."
        logger.warning(msg)
        return {"success": False, "error": "MISSING_CREDENTIALS", "message": msg}

    # Si no se pasó reply_markup, usar el panel interactivo estándar
    markup_to_use = reply_markup if reply_markup is not None else build_interactive_keyboard()

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"

    async with httpx.AsyncClient(timeout=30.0) as client:
        with open(target_photo, "rb") as img_file:
            files = {"photo": (target_photo.name, img_file, "image/png")}
            data: Dict[str, Any] = {
                "chat_id": target_chat,
                "reply_markup": json.dumps(markup_to_use)
            }
            if final_caption.strip():
                data["caption"] = final_caption
                if parse_mode:
                    data["parse_mode"] = parse_mode
            if reply_to_message_id:
                data["reply_to_message_id"] = reply_to_message_id

            try:
                response = await client.post(telegram_url, data=data, files=files)
                res_json = response.json()
                if response.status_code == 200 and res_json.get("ok"):
                    logger.info("Imagen enviada exitosamente a Telegram.")
                    return {"success": True, "result": res_json}

                logger.error(f"Error en respuesta de Telegram API: {res_json}")
                return {"success": False, "error": res_json}
            except Exception as e:
                logger.error(f"Fallo en la conexión con la API de Telegram: {e}")
                return {"success": False, "error": str(e)}


# ============================================================================
# Handlers de Acciones Interactivas
# ============================================================================

def _resolve_target_trend(trend_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Recupera la tendencia objetivo por su ID o selecciona la última enviada."""
    if trend_id is not None:
        trend = get_trend_by_id(trend_id)
        if trend:
            return trend
    recent = get_recent_sent_trends(limit=1)
    return recent[0] if recent else None


async def handle_save_trend(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None,
    message_id: Optional[int] = None
) -> None:
    """1. '⭐ Guardar en favoritos': Almacena la tendencia en SQLite y asocia el message_id de Telegram."""
    trend = _resolve_target_trend(trend_id)
    if not trend:
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="No se encontró la tendencia para guardar.", show_alert=True)
        return

    tid = trend["id"]
    title = trend["title"]
    mark_as_favorite(tid, message_id=message_id)

    if callback_query_id:
        await answer_callback_query(callback_query_id, text="⭐ ¡Guardado en tus favoritos!", show_alert=False)

    msg = (
        f"⭐ <b>Guardado en tus favoritos</b>\n\n"
        f"La tecnología <b>{title}</b> ha sido almacenada correctamente en tu lista de favoritos.\n\n"
        f"Puedes consultarla cuando desees con el botón <b>📁 Ver favoritos</b> o el comando <code>/favoritos</code>."
    )
    await send_telegram_message(text=msg, chat_id=chat_id)


async def handle_view_favorites(
    chat_id: str,
    callback_query_id: Optional[str] = None
) -> None:
    """1. Eliminar Imagen de Favoritos: Responde solo con texto limpio y botones dinámicos para cada favorito."""
    if callback_query_id:
        await answer_callback_query(callback_query_id)

    favs = get_favorites()
    if not favs:
        empty_msg = (
            "📁 <b>Portafolio de Favoritos</b>\n\n"
            "Aún no tienes tecnologías guardadas en tus favoritos.\n\n"
            "Utiliza el botón <b>⭐ Guardar en favoritos</b> en el radar diario para guardar las soluciones más relevantes."
        )
        await send_telegram_message(text=empty_msg, chat_id=chat_id)
        return

    # 2. Botones Dinámicos: genera un botón por cada tendencia guardada con LOAD_FAV_{id}
    buttons = []
    for f in favs:
        btn_text = f"📍 {f['title']}"
        buttons.append([
            {"text": btn_text, "callback_data": f"LOAD_FAV_{f['id']}"}
        ])

    # Botones complementarios
    buttons.append([
        {"text": "📈 Gráfica de tendencias", "callback_data": "GET_CHART"},
        {"text": "🚀 Forzar nuevo radar", "callback_data": "RUN_RADAR"}
    ])

    text = (
        "📁 <b>Portafolio de Favoritos:</b>\n\n"
        "Toca una tecnología para recuperar y saltar a su tarjeta visual original:"
    )

    await send_telegram_message(
        text=text,
        chat_id=chat_id,
        reply_markup={"inline_keyboard": buttons}
    )


async def handle_load_favorite(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    fav_id: Optional[int] = None
) -> None:
    """3. Recuperación de Tarjeta Original: Consulta message_id en SQLite y envía mensaje corto con reply_to_message_id."""
    favs = get_favorites()
    target_fav = next((f for f in favs if f["id"] == fav_id), None)
    if not target_fav and favs:
        target_fav = favs[0]

    if not target_fav:
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="No se encontró la tendencia seleccionada.", show_alert=True)
        return

    msg_id = target_fav.get("message_id")
    title = target_fav.get("title", "Tendencia")

    if callback_query_id:
        await answer_callback_query(callback_query_id, text=f"📍 Recuperando {title}...")

    reply_text = (
        f"Aquí tienes tu tendencia guardada: <b>{title}</b>\n\n"
        f"👆 <i>Toca la cita superior para ver la tarjeta visual original.</i>"
    )

    await send_telegram_message(
        text=reply_text,
        chat_id=chat_id,
        reply_to_message_id=msg_id,
        reply_markup={
            "inline_keyboard": [
                [
                    {"text": "🔍 Profundizar datos", "callback_data": f"DEEP_DIVE:{target_fav['id']}"},
                    {"text": "📁 Ver favoritos", "callback_data": "VIEW_FAVS"}
                ]
            ]
        }
    )


async def handle_get_chart(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None
) -> None:
    """3. '📈 Gráfica de tendencias': Renderiza con Playwright tarjeta_grafica.html y envía el PNG."""
    if callback_query_id:
        await answer_callback_query(callback_query_id, text="📈 Generando gráfica de tracción...")

    chart_target = settings.BASE_DIR / "temp_chart.png"
    try:
        await create_chart_png_card(output_path=chart_target)
        caption = (
            "📈 <b>Radar de Tracción & Demanda B2B</b>\n\n"
            "Análisis comparativo de volumen, crecimiento sostenido y aceleración comercial "
            "monitoreado en tiempo real a través de fuentes abiertas (Product Hunt, Hacker News, Reddit y Google Trends)."
        )
        await send_telegram_notification(
            photo_path=chart_target,
            caption=caption,
            chat_id=chat_id,
            reply_markup=build_interactive_keyboard(trend_id)
        )
    except Exception as e:
        logger.error(f"Error generando o enviando gráfica de tracción: {e}")
        await send_telegram_message(
            text=f"⚠️ No se pudo renderizar la gráfica de tendencias: {e}",
            chat_id=chat_id
        )


async def handle_deep_dive(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None
) -> None:
    """4. '🔍 Profundizar datos': Genera reporte técnico y comercial denso y exhaustivo con Gemma."""
    if callback_query_id:
        await answer_callback_query(callback_query_id, text="🔍 Generando reporte técnico y comercial...")

    trend = _resolve_target_trend(trend_id)
    if not trend:
        await send_telegram_message(
            text="⚠️ No se encontraron datos para generar el reporte profundo.",
            chat_id=chat_id
        )
        return

    from app.llm_service import generate_deep_dive_report
    report = await generate_deep_dive_report(trend)
    await send_telegram_message(
        text=report,
        chat_id=chat_id,
        parse_mode="HTML"
    )


async def process_telegram_update(update: Dict[str, Any]) -> None:
    """Procesa una actualización entrante de Telegram (CallbackQuery o Message)."""
    # 1. Manejo de Botones del Inline Keyboard
    if "callback_query" in update:
        cq = update["callback_query"]
        cb_id = cq["id"]
        data = cq.get("data", "")
        msg_obj = cq.get("message", {})
        user_chat_id = str(msg_obj.get("chat", {}).get("id"))
        orig_msg_id = msg_obj.get("message_id")

        # 3. Manejo de LOAD_FAV_{id}
        if data.startswith("LOAD_FAV_"):
            fav_id_str = data.replace("LOAD_FAV_", "")
            fav_id = int(fav_id_str) if fav_id_str.isdigit() else None
            await handle_load_favorite(chat_id=user_chat_id, callback_query_id=cb_id, fav_id=fav_id)
            return

        # Extraer trend_id si viene en el callback_data
        parts = data.split(":")
        action = parts[0]
        trend_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None

        if action in ("SAVE_TREND", "save_favorite"):
            await handle_save_trend(
                chat_id=user_chat_id,
                callback_query_id=cb_id,
                trend_id=trend_id,
                message_id=orig_msg_id
            )
        elif action in ("VIEW_FAVS", "view_favorites"):
            await handle_view_favorites(chat_id=user_chat_id, callback_query_id=cb_id)
        elif action in ("LOAD_FAV", "GOTO_FAV", "goto_fav"):
            await handle_load_favorite(chat_id=user_chat_id, callback_query_id=cb_id, fav_id=trend_id)
        elif action in ("GET_CHART", "view_chart"):
            await handle_get_chart(chat_id=user_chat_id, callback_query_id=cb_id, trend_id=trend_id)
        elif action in ("DEEP_DIVE", "deep_dive"):
            await handle_deep_dive(chat_id=user_chat_id, callback_query_id=cb_id, trend_id=trend_id)
        elif action in ("RUN_RADAR", "run_radar"):
            await answer_callback_query(cb_id, text="🚀 Ejecutando radar diario...")
            from app.main import run_daily_pipeline
            asyncio.create_task(run_daily_pipeline())
        else:
            await answer_callback_query(cb_id, text="Acción recibida.")
        return

    # 2. Manejo de Mensajes de Texto (Comandos)
    if "message" in update:
        msg = update["message"]
        text = str(msg.get("text", "")).strip()
        user_chat_id = str(msg.get("chat", {}).get("id"))

        if not text:
            return

        logger.info(f"[Telegram Bot] Mensaje recibido: '{text}' de chat_id={user_chat_id}")

        if text.startswith("/favoritos"):
            await handle_view_favorites(chat_id=user_chat_id)
        elif text.startswith("/grafica") or text.startswith("/chart"):
            await handle_get_chart(chat_id=user_chat_id)
        elif text.startswith("/profundizar") or text.startswith("/deepdive"):
            await handle_deep_dive(chat_id=user_chat_id)
        elif text.startswith("/start") or text.startswith("/help") or text.startswith("/ayuda"):
            welcome = (
                "👋 <b>Bienvenido al Agente de Inteligencia Comercial B2B</b>\n\n"
                "Monitoreo diario automatizado de tendencias tecnológicas de alto impacto comercial.\n\n"
                "<b>Comandos disponibles:</b>\n"
                "• <code>/radar</code> o <code>/hoy</code> : Generar y enviar el radar de hoy inmediatamente.\n"
                "• <code>/favoritos</code> : Listar todas tus tecnologías guardadas con enlaces a sus tarjetas.\n"
                "• <code>/grafica</code> : Visualizar la gráfica de tracción semanal.\n"
                "• <code>/profundizar</code> : Generar reporte denso sobre la última tecnología.\n\n"
                "<i>También puedes interactuar directamente usando los botones debajo de cada tarjeta.</i>"
            )
            await send_telegram_message(text=welcome, chat_id=user_chat_id)
        elif text.startswith("/radar") or text.startswith("/hoy"):
            await send_telegram_message(
                text="🚀 <i>Ejecutando el radar diario de inteligencia comercial... Te enviaré la tarjeta en un momento.</i>",
                chat_id=user_chat_id
            )
            from app.main import run_daily_pipeline
            asyncio.create_task(run_daily_pipeline())


# ============================================================================
# Long Polling en Segundo Plano
# ============================================================================

async def _poll_loop() -> None:
    """Bucle infinito de Long Polling para escuchar eventos de Telegram en tiempo real."""
    global _polling_active
    bot_token, _ = _get_credentials()
    if not bot_token:
        logger.warning("[Telegram Bot] TELEGRAM_BOT_TOKEN no configurado. Polling desactivado.")
        return

    # Limpiar webhook existente para permitir long polling sin conflicto
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(f"https://api.telegram.org/bot{bot_token}/deleteWebhook")
        except Exception:
            pass

    offset = 0
    logger.info("[Telegram Bot] Long Polling iniciado exitosamente. Escuchando eventos...")

    while _polling_active:
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
                params = {"offset": offset, "timeout": 15}
                resp = await client.get(url, params=params)

                if resp.status_code == 200:
                    data = resp.json()
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        asyncio.create_task(process_telegram_update(update))
                else:
                    await asyncio.sleep(2)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"[Telegram Bot] Excepción en polling (reconectando): {e}")
            await asyncio.sleep(3)

    logger.info("[Telegram Bot] Long Polling detenido.")


async def start_bot_polling() -> None:
    """Inicia el listener de Long Polling en una tarea en segundo plano."""
    global _polling_active, _polling_task
    if _polling_active:
        return
    _polling_active = True
    _polling_task = asyncio.create_task(_poll_loop())


async def stop_bot_polling() -> None:
    """Detiene limpiamente el listener de Long Polling."""
    global _polling_active, _polling_task
    _polling_active = False
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None
