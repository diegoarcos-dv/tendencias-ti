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
import time
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv

from app.config import settings
from app.database import (
    mark_as_favorite,
    add_favorite,
    remove_favorite,
    get_favorites,
    get_trend_by_id,
    get_favorite_or_trend,
    get_recent_sent_trends,
    get_user_zone,
    set_user_zone,
    record_sent_card,
    get_user_daily_card_count,
    get_last_sent_card_message,
)
from app.visual_engine import create_chart_png_card

logger = logging.getLogger("app.telegram_bot")

_polling_active = False
_polling_task: Optional[asyncio.Task] = None

# Cliente HTTP persistente para evitar handshakes TLS repetitivos
_http_client: Optional[httpx.AsyncClient] = None

# Caché en memoria y persistente del file_id de Telegram para gráfica y tarjetas
_chart_file_id_cache: Dict[str, str] = {}
_trend_card_file_id_cache: Dict[Any, str] = {}
_CATALOG_CACHE_FILE = settings.DATA_DIR / "telegram_file_cache.json"


def _load_catalog_file_id_cache() -> Dict[str, str]:
    if _CATALOG_CACHE_FILE.exists():
        try:
            with open(_CATALOG_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_catalog_file_id_cache(cache: Dict[str, str]) -> None:
    try:
        _CATALOG_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_CATALOG_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"Error persistiendo telegram_file_cache.json: {e}")


_catalog_file_id_cache: Dict[str, str] = _load_catalog_file_id_cache()


def set_catalog_cached_file_id(key: str, file_id: str) -> None:
    """Registra un file_id de Telegram en la caché de catálogo para navegación instantánea."""
    if file_id:
        _catalog_file_id_cache[str(key)] = str(file_id)
        _save_catalog_file_id_cache(_catalog_file_id_cache)


def get_catalog_cached_file_id(key: str) -> Optional[str]:
    """Obtiene un file_id de Telegram de la caché de catálogo."""
    return _catalog_file_id_cache.get(str(key))


def get_http_client() -> httpx.AsyncClient:
    """Retorna una instancia persistente de httpx.AsyncClient con conexión persistente (pooling)."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def close_http_client() -> None:
    """Cierra la conexión HTTP persistente."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None


def clear_chart_cache() -> None:
    """Invalida la caché de la gráfica manteniendo los file_id vigentes de hoy para respuesta < 100ms."""
    global _chart_file_id_cache, _catalog_file_id_cache
    _chart_file_id_cache.clear()
    _catalog_file_id_cache.pop("chart_traction", None)

    # Conservar file_ids del día actual (today_str) para navegación instantánea sin subir 3MB de nuevo
    from datetime import timezone
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    keys_to_remove = [
        k for k in list(_catalog_file_id_cache.keys())
        if (k.startswith("events_cdmx") or k.startswith("demand_b2b")) and today_str not in k
    ]
    for k in keys_to_remove:
        _catalog_file_id_cache.pop(k, None)
    _save_catalog_file_id_cache(_catalog_file_id_cache)
    logger.info("[Telegram Bot] Caché de file_id actualizada (preservando activos de hoy para velocidad instantánea).")


def _get_credentials() -> tuple[str, str]:
    """Carga y retorna (bot_token, chat_id) desde las variables de entorno."""
    load_dotenv(settings.BASE_DIR / ".env", override=True)
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or settings.TELEGRAM_BOT_TOKEN
    chat_id = os.getenv("TELEGRAM_CHAT_ID") or settings.TELEGRAM_CHAT_ID
    return bot_token, chat_id


def build_interactive_keyboard(
    trend_id: Optional[int] = None,
    source_url: Optional[str] = None,
    showing_chart: bool = False,
    current_index: Optional[int] = None,
    total_items: Optional[int] = None
) -> Dict[str, Any]:
    """Genera la estructura del panel interactivo para chats privados (DM) con los botones interactivos:
    - ◀️ Anterior | 📌 N de Total | Siguiente ▶️ (carrusel de tendencias)
    - 📈 Ver gráfica / 📍 Tendencia original (alternable binario)
    - 🛠️ Stack técnico (callback_data: GET_STACK)
    - ⭐ Guardar en favoritos (callback_data: SAVE_TREND)
    - 🔍 Profundizar datos (callback_data: DEEP_DIVE)
    - 💼 Proyectos Freelance (callback_data: GET_FREELANCE)
    - 📁 Mis favoritos (callback_data: VIEW_FAVS)
    - ⚡ Nueva tendencia ahora (callback_data: RUN_RADAR)
    - ⚙️ Configuración (callback_data: RESET_CONFIG)
    """
    id_suffix = f":{trend_id}" if trend_id is not None else ""
    chart_btn_text = "📍 Tendencia original" if showing_chart else "📈 Ver gráfica"
    chart_cb = f"TOGGLE_DM_ORIGINAL{id_suffix}" if showing_chart else f"GET_CHART{id_suffix}"

    rows = []

    # Fila 1: Paginación de carrusel (si hay múltiples tendencias)
    if total_items and total_items > 1 and current_index is not None:
        idx = current_index % total_items
        rows.append([
            {"text": "◀️ Anterior", "callback_data": f"CATALOG_NAV:prev:{idx}"},
            {"text": f"📌 {idx + 1} de {total_items}", "callback_data": f"CATALOG_INFO:{idx}"},
            {"text": "Siguiente ▶️", "callback_data": f"CATALOG_NAV:next:{idx}"}
        ])

    # Fila 2: Gráfica y Stack
    rows.append([
        {"text": chart_btn_text, "callback_data": chart_cb},
        {"text": "🛠️ Stack técnico", "callback_data": f"GET_STACK{id_suffix}"}
    ])

    # Fila 3: Demanda B2B y Eventos CDMX
    curr_i = (current_index or 0) % (total_items or 1)
    rows.append([
        {"text": "🏢 Demanda", "callback_data": f"NAV_DEMANDA:{curr_i}"},
        {"text": "🎟️ Eventos CDMX", "callback_data": f"NAV_EVENTOS:{curr_i}"}
    ])

    # Fila 4: Guardar en favoritos y Profundizar datos
    rows.append([
        {"text": "⭐ Guardar en favoritos", "callback_data": f"SAVE_TREND{id_suffix}"},
        {"text": "🔍 Profundizar datos", "callback_data": f"DEEP_DIVE{id_suffix}"}
    ])

    # Fila 4: Mis favoritos y Generar ahora
    rows.append([
        {"text": "📁 Mis favoritos", "callback_data": "VIEW_FAVS"},
        {"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR"}
    ])

    # Fila 5: Configuración
    rows.append([
        {"text": "⚙️ Configuración", "callback_data": "RESET_CONFIG"}
    ])

    # Fila 6: Botón único para regresar al grupo público (Rama A)
    group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID", "-1004339114906")
    if group_chat_id:
        clean_cid = str(group_chat_id).replace("-100", "").lstrip("-")
        group_url = f"https://t.me/c/{clean_cid}"
        rows.append([
            {"text": "👥 Ir al Grupo TI", "url": group_url}
        ])

    return {"inline_keyboard": rows}


def update_dm_keyboard_chart_toggle(
    current_reply_markup: Optional[Dict[str, Any]],
    showing_chart: bool,
    trend_id: Optional[int] = None
) -> Dict[str, Any]:
    """Actualiza únicamente el botón de la gráfica en el teclado DM existente:
    - Si showing_chart=True -> '📍 Tendencia original'
    - Si showing_chart=False -> '📈 Ver gráfica'
    Manteniendo intactos los botones de favoritos, menú, configuración, stack y profundizar.
    """
    id_suffix = f":{trend_id}" if trend_id is not None else ""
    target_text = "📍 Tendencia original" if showing_chart else "📈 Ver gráfica"
    target_cb = f"TOGGLE_DM_ORIGINAL{id_suffix}" if showing_chart else f"GET_CHART{id_suffix}"

    if current_reply_markup and "inline_keyboard" in current_reply_markup:
        import copy
        new_kb = copy.deepcopy(current_reply_markup)
        updated = False
        for row in new_kb["inline_keyboard"]:
            for btn in row:
                cb = btn.get("callback_data", "")
                txt = btn.get("text", "")
                if (
                    cb.startswith("GET_CHART")
                    or cb.startswith("TOGGLE_DM_ORIGINAL")
                    or "gráfica" in txt.lower()
                    or "grafica" in txt.lower()
                    or "tendencia original" in txt.lower()
                ):
                    btn["text"] = target_text
                    btn["callback_data"] = target_cb
                    updated = True
                    break
            if updated:
                break
        if updated:
            return new_kb

    return build_interactive_keyboard(trend_id=trend_id, showing_chart=showing_chart)


def build_group_keyboard(
    trend_id: Optional[Any] = None,
    bot_username: Optional[str] = None,
    showing_chart: bool = False
) -> Dict[str, Any]:
    """Genera el teclado para grupos/supergrupos:
    - Botón '🔍 Profundizar' configurado como deep-link URL (t.me/TuBot?start=deepdive_{trend_id})
    - Botón '🤖 Personalizar alertas' configurado como deep-link URL (t.me/TuBot?start=config)
    - Botón de alternancia:
      * Estado 1 (Imagen Original): [ 📈 Gráfica de tendencias ] (TOGGLE_CHART_{trend_id})
      * Estado 2 (Imagen Gráfica): [ 📍 Tendencia original ] (TOGGLE_CHART_{trend_id}:original)
    """
    if isinstance(trend_id, str) and not trend_id.isdigit():
        bot_username = trend_id
        trend_id = None

    username = bot_username or settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot"
    clean_username = username.lstrip("@")
    tid_str = str(trend_id) if trend_id is not None else ""
    deepdive_url = f"https://t.me/{clean_username}?start=deepdive_{tid_str}"
    config_url = f"https://t.me/{clean_username}?start=config"

    if showing_chart:
        return build_chart_keyboard(return_index=0)
    return build_catalog_keyboard(current_index=0, total_items=5, trend_id=trend_id, bot_username=bot_username)


def build_catalog_keyboard(
    current_index: int = 0,
    total_items: int = 5,
    trend_id: Optional[Any] = None,
    bot_username: Optional[str] = None
) -> Dict[str, Any]:
    """Genera el teclado interactivo del Catálogo con diseño limpio y sin saturación:
    - Fila 1 (Carrusel compacto): [ ◀️ ] [ 📍 X / Total ] [ ▶️ ]
    - Fila 2 (Detalles):          [ 📈 Gráfica ] [ 🛠️ Stack ]
    - Fila 3 (Categorías):        [ 🏢 Demanda B2B ] [ 🎟️ Eventos CDMX ]
    - Fila 4 (Personalización):   [ ⚙️ Personalizar radar ] -> Chatbot en privado
    """
    total = max(1, total_items)
    idx = current_index % total
    tid_str = str(trend_id) if trend_id is not None else ""
    username = (bot_username or settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
    config_url = f"https://t.me/{username}?start=config"
    stack_url = f"https://t.me/{username}?start=stack_{tid_str}"

    return {
        "inline_keyboard": [
            [
                {"text": "◀️", "callback_data": f"CATALOG_NAV:prev:{idx}"},
                {"text": f"📍 {idx + 1} / {total}", "callback_data": f"CATALOG_INFO:{idx}"},
                {"text": "▶️", "callback_data": f"CATALOG_NAV:next:{idx}"}
            ],
            [
                {"text": "📈 Gráfica", "callback_data": f"CATALOG_CHART:{idx}:{tid_str}"},
                {"text": "🛠️ Stack", "url": stack_url}
            ],
            [
                {"text": "🏢 Demanda", "callback_data": f"NAV_DEMANDA:{idx}"},
                {"text": "🎟️ Eventos CDMX", "callback_data": f"NAV_EVENTOS:{idx}"}
            ],
            [
                {"text": "⚙️ Personalizar radar", "url": config_url}
            ]
        ]
    }


def build_demand_keyboard(
    current_index: int = 0,
    total_items: int = 5,
    return_index: int = 0,
    company_linkedin_url: Optional[str] = None,
    company_web_url: Optional[str] = None,
    linkedin_status: str = "active"
) -> Dict[str, Any]:
    """Teclado interactivo para Catálogo de Empresas Demandantes B2B:
    - Fila 1: Paginación de empresas
    - Fila 2: Ver Alcance & SOW (Deep-link directo al chat privado de la Rama B)
    - Fila 3: Opción 2 - Simular Cotización & Margen TI (Deep-link directo al chat privado de la Rama B)
    - Fila 4: Opción C - Perfil Oficial en LinkedIn de la Empresa (con fallback automático a Web Oficial)
    - Fila 5: Volver a Inicio
    """
    total = max(1, total_items)
    idx = current_index % total
    username = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
    scope_url = f"https://t.me/{username}?start=scope_{idx}_{return_index}"
    quote_url = f"https://t.me/{username}?start=quote_{idx}_{return_index}"

    # Fila 4: Perfil de LinkedIn o Fallback automático a Sitio Web Oficial si LinkedIn no está disponible
    if linkedin_status == "active" and company_linkedin_url and "linkedin.com" in company_linkedin_url:
        company_btn = {"text": "🏢 Perfil Oficial en LinkedIn", "url": company_linkedin_url}
    else:
        web_url = company_web_url or "https://www.google.com"
        if not web_url.startswith("http://") and not web_url.startswith("https://"):
            web_url = f"https://{web_url}"
        company_btn = {"text": "🌐 Sitio Web Oficial", "url": web_url}

    return {
        "inline_keyboard": [
            [
                {"text": "◀️", "callback_data": f"NAV_DEMANDA_PAGE:prev:{idx}:{return_index}"},
                {"text": f"🏢 Empresa {idx + 1} / {total}", "callback_data": f"DEMANDA_INFO:{idx}"},
                {"text": "▶️", "callback_data": f"NAV_DEMANDA_PAGE:next:{idx}:{return_index}"}
            ],
            [
                {"text": "📋 Ver Alcance & SOW", "url": scope_url}
            ],
            [
                {"text": "📊 Simular Cotización & Margen TI", "url": quote_url}
            ],
            [
                company_btn
            ],
            [
                {"text": "🏠 Inicio", "callback_data": f"CATALOG_GOTO:{return_index}"}
            ]
        ]
    }


def build_events_keyboard(
    current_index: int = 0,
    total_items: int = 5,
    return_index: int = 0,
    registration_url: Optional[str] = None
) -> Dict[str, Any]:
    """Teclado interactivo para Calendario de Eventos TI CDMX (especial jóvenes) con paginación."""
    total = max(1, total_items)
    idx = current_index % total
    url = registration_url or "https://lu.ma/mxtw"
    return {
        "inline_keyboard": [
            [
                {"text": "◀️", "callback_data": f"NAV_EVENTOS_PAGE:prev:{idx}:{return_index}"},
                {"text": f"📅 Evento {idx + 1} / {total}", "callback_data": f"EVENTOS_INFO:{idx}"},
                {"text": "▶️", "callback_data": f"NAV_EVENTOS_PAGE:next:{idx}:{return_index}"}
            ],
            [
                {"text": "📋 Ver Logística & Dinámica", "callback_data": f"EVENTOS_DETAILS:{idx}:{return_index}"}
            ],
            [
                {"text": "🎟️ Enlace Directo de Registro", "url": url}
            ],
            [
                {"text": "🏠 Inicio", "callback_data": f"CATALOG_GOTO:{return_index}"}
            ]
        ]
    }


def build_chart_keyboard(return_index: int = 0) -> Dict[str, Any]:
    """Teclado contextual para Gráfica con botón Inicio claro."""
    return {
        "inline_keyboard": [
            [
                {"text": "🏠 Inicio", "callback_data": f"CATALOG_GOTO:{return_index}"}
            ]
        ]
    }







async def edit_telegram_media(
    chat_id: str | int,
    message_id: int,
    photo_path: Path | str,
    reply_markup: Optional[Dict[str, Any]] = None,
    caption: str = ""
) -> Dict[str, Any]:
    """Edita la imagen de un mensaje existente en Telegram utilizando el método nativo editMessageMedia (cero spam)."""
    bot_token, _ = _get_credentials()
    if not bot_token:
        logger.error("[editMessageMedia] Bot token no configurado.")
        return {"success": False, "error": "No token"}

    url = f"https://api.telegram.org/bot{bot_token}/editMessageMedia"
    client = get_http_client()

    is_file_id = isinstance(photo_path, str) and not Path(photo_path).exists() and not photo_path.endswith((".png", ".jpg", ".jpeg"))

    try:
        if is_file_id:
            media_obj = {
                "type": "photo",
                "media": str(photo_path),
                "caption": caption
            }
            data: Dict[str, Any] = {
                "chat_id": str(chat_id),
                "message_id": int(message_id),
                "media": json.dumps(media_obj)
            }
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)
            resp = await client.post(url, data=data, timeout=30.0)
        else:
            p = Path(photo_path)
            if not p.exists():
                logger.error(f"[editMessageMedia] Archivo no encontrado: {p}")
                return {"success": False, "error": f"File not found: {p}"}

            media_obj = {
                "type": "photo",
                "media": "attach://photo_file",
                "caption": caption
            }
            data = {
                "chat_id": str(chat_id),
                "message_id": int(message_id),
                "media": json.dumps(media_obj)
            }
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)

            with open(p, "rb") as f:
                files = {"photo_file": (p.name, f, "image/png")}
                resp = await client.post(url, data=data, files=files, timeout=30.0)

        res_json = resp.json()
        if resp.status_code == 200 and res_json.get("ok"):
            logger.info(f"[editMessageMedia] Mensaje {message_id} en {chat_id} actualizado exitosamente.")
            photos = res_json.get("result", {}).get("photo", [])
            returned_file_id = photos[-1].get("file_id") if photos else (str(photo_path) if is_file_id else None)
            return {"success": True, "result": res_json, "file_id": returned_file_id}
        elif "message is not modified" in str(res_json.get("description", "")):
            logger.debug(f"[editMessageMedia] Mensaje {message_id} ya tenía este contenido exacto.")
            return {"success": True, "result": res_json, "file_id": str(photo_path) if is_file_id else None}
        else:
            logger.error(f"[editMessageMedia] Error de Telegram ({resp.status_code}): {res_json}")
            return {"success": False, "error": res_json}
    except Exception as e:
        logger.error(f"[editMessageMedia] Excepción en editMessageMedia: {e}")
        return {"success": False, "error": str(e)}


async def delete_telegram_message(chat_id: str, message_id: int) -> bool:
    """Elimina un mensaje de Telegram utilizando el método deleteMessage de la API oficial."""
    bot_token, _ = _get_credentials()
    if not bot_token:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/deleteMessage"
    try:
        client = get_http_client()
        resp = await client.post(url, json={"chat_id": str(chat_id), "message_id": int(message_id)})
        data = resp.json()
        if resp.status_code == 200 and data.get("ok"):
            logger.info(f"Mensaje {message_id} en chat {chat_id} eliminado exitosamente.")
            return True
        logger.warning(f"No se pudo eliminar mensaje {message_id} en {chat_id}: {data}")
        return False
    except Exception as e:
        logger.error(f"Error llamando a deleteMessage para chat {chat_id}, msg {message_id}: {e}")
        return False



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
        client = get_http_client()
        resp = await client.post(url, json=payload)
        return resp.status_code == 200
    except Exception as e:
        logger.warning(f"Error respondiendo callback_query: {e}")
        return False


async def edit_telegram_message_text(
    chat_id: str | int,
    message_id: int,
    text: str,
    reply_markup: Optional[Dict[str, Any]] = None,
    parse_mode: Optional[str] = "HTML"
) -> Dict[str, Any]:
    """Edita el texto y/o botones de un mensaje existente en Telegram utilizando editMessageText."""
    bot_token, _ = _get_credentials()
    if not bot_token:
        return {"success": False, "error": "MISSING_CREDENTIALS"}

    url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
    payload: Dict[str, Any] = {
        "chat_id": str(chat_id),
        "message_id": int(message_id),
        "text": text,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        client = get_http_client()
        resp = await client.post(url, json=payload)
        res_json = resp.json()
        if resp.status_code == 200 and res_json.get("ok"):
            return {"success": True, "result": res_json}
        if "can't parse entities" in str(res_json.get("description", "")):
            import re
            plain_text = re.sub(r"<[^>]+>", "", text)
            payload["text"] = plain_text
            payload.pop("parse_mode", None)
            retry_resp = await client.post(url, json=payload)
            return {"success": retry_resp.status_code == 200, "result": retry_resp.json()}
        return {"success": False, "error": res_json}
    except Exception as e:
        logger.error(f"Error editando mensaje de Telegram ({chat_id}, {message_id}): {e}")
        return {"success": False, "error": str(e)}


async def edit_telegram_reply_markup(
    chat_id: str | int,
    message_id: int,
    reply_markup: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Actualiza únicamente el teclado en línea (Inline Keyboard) de un mensaje existente utilizando editMessageReplyMarkup."""
    bot_token, _ = _get_credentials()
    if not bot_token:
        return {"success": False, "error": "MISSING_CREDENTIALS"}

    url = f"https://api.telegram.org/bot{bot_token}/editMessageReplyMarkup"
    payload: Dict[str, Any] = {
        "chat_id": str(chat_id),
        "message_id": int(message_id),
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        client = get_http_client()
        resp = await client.post(url, json=payload)
        res_json = resp.json()
        if resp.status_code == 200 and res_json.get("ok"):
            return {"success": True, "result": res_json}
        return {"success": False, "error": res_json}
    except Exception as e:
        logger.error(f"Error en editMessageReplyMarkup ({chat_id}, {message_id}): {e}")
        return {"success": False, "error": str(e)}


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
        for idx, chunk in enumerate(chunks):
            # Adjuntar reply_markup solo al último chunk
            chunk_markup = reply_markup if idx == len(chunks) - 1 else None
            chunk_reply_to = reply_to_message_id if idx == 0 else None
            last_res = await send_telegram_message(
                text=chunk,
                chat_id=chat_id,
                parse_mode=parse_mode,
                reply_markup=chunk_markup,
                reply_to_message_id=chunk_reply_to
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
        client = get_http_client()
        resp = await client.post(url, json=payload)
        res_json = resp.json()
        if resp.status_code == 200 and res_json.get("ok"):
            return {"success": True, "result": res_json}

        if res_json.get("parameters", {}).get("migrate_to_chat_id"):
            migrated_id = str(res_json["parameters"]["migrate_to_chat_id"])
            payload["chat_id"] = migrated_id
            retry_migrated = await client.post(url, json=payload)
            if retry_migrated.status_code == 200 and retry_migrated.json().get("ok"):
                return {"success": True, "result": retry_migrated.json()}

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


async def send_chat_action(
    action: str = "typing",
    chat_id: Optional[str] = None
) -> bool:
    """Envía una acción de chat (typing, upload_photo, etc.) a Telegram para feedback inmediato al usuario."""
    bot_token, default_chat = _get_credentials()
    target_chat = chat_id or default_chat
    if not bot_token or not target_chat:
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    payload = {"chat_id": target_chat, "action": action}
    try:
        client = get_http_client()
        resp = await client.post(url, json=payload, timeout=5.0)
        return resp.status_code == 200
    except Exception as e:
        logger.debug(f"Error en sendChatAction ({target_chat}, {action}): {e}")
        return False


async def send_telegram_notification(
    photo_path: Optional[Path | str] = None,
    caption: Optional[str] = None,
    reply_markup: Optional[Dict[str, Any]] = None,
    chat_id: Optional[str] = None,
    parse_mode: Optional[str] = "HTML",
    reply_to_message_id: Optional[int] = None,
    chat_type: Optional[str] = None,
    trend_id: Optional[int] = None,
    fallback_activado: bool = False,
    zona_local: Optional[str] = None,
    zona_pais: Optional[str] = None
) -> Dict[str, Any]:
    """Envía una imagen (tarjeta PNG) a Telegram con la UI condicional según el entorno (Grupo vs DM)."""
    bot_token, default_chat = _get_credentials()
    target_chat = chat_id or default_chat

    is_file_id = False
    if isinstance(photo_path, str) and not Path(photo_path).exists():
        is_file_id = True
        target_photo = None
    elif photo_path is None:
        target_photo = settings.BASE_DIR / "temp_card.png"
        if not target_photo.exists():
            raise FileNotFoundError(f"Imagen no encontrada para envío: {target_photo}")
    else:
        target_photo = Path(photo_path)
        if not target_photo.exists():
            raise FileNotFoundError(f"Imagen no encontrada para envío: {target_photo}")

    final_caption = caption if caption is not None else ""
    if fallback_activado and zona_local and zona_pais:
        fallback_msg = f"📍 *Nota del radar: No detectamos volumen suficiente de datos en {zona_local} hoy, por lo que hemos ampliado el análisis a nivel {zona_pais}.*"
        if fallback_msg not in final_caption:
            final_caption = f"{fallback_msg}\n\n{final_caption}".strip() if final_caption else fallback_msg
        if parse_mode != "Markdown":
            parse_mode = "Markdown"

    if not bot_token or not target_chat:
        msg = "⚠️ TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID no configurados."
        logger.warning(msg)
        return {"success": False, "error": "MISSING_CREDENTIALS", "message": msg}

    resolved_chat_type = chat_type or ("group" if str(target_chat).startswith("-") else "private")

    # DETERMINAR TECLADO OBLIGATORIO:
    if reply_markup is not None:
        markup_to_use = reply_markup
    else:
        if resolved_chat_type in ("group", "supergroup"):
            markup_to_use = build_group_keyboard(trend_id=trend_id)
        else:
            markup_to_use = build_interactive_keyboard(trend_id=trend_id)

    # REGLA ESTRICTA: SIEMPRE asegurar que el payload incluya el InlineKeyboardMarkup correspondiente
    if not markup_to_use:
        markup_to_use = build_interactive_keyboard(trend_id=trend_id)

    markup_json = json.dumps(markup_to_use) if isinstance(markup_to_use, dict) else str(markup_to_use)

    candidate_chats = [str(target_chat)]
    if str(target_chat).startswith("-") and not str(target_chat).startswith("-100"):
        candidate_chats.append(f"-100{str(target_chat).lstrip('-')}")

    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
    client = get_http_client()
    last_error = {}

    for c_chat in candidate_chats:
        # Enviar foto, caption (resumen) y reply_markup en la misma llamada HTTP POST
        data: Dict[str, Any] = {
            "chat_id": c_chat,
            "reply_markup": markup_json
        }
        if final_caption.strip():
            data["caption"] = final_caption
            if parse_mode:
                data["parse_mode"] = parse_mode
        if reply_to_message_id:
            data["reply_to_message_id"] = reply_to_message_id

        try:
            if is_file_id:
                data["photo"] = str(photo_path)
                response = await client.post(telegram_url, data=data)
            else:
                with open(target_photo, "rb") as img_file:
                    files = {"photo": (target_photo.name, img_file, "image/png")}
                    response = await client.post(telegram_url, data=data, files=files)

            res_json = response.json()
            if res_json.get("parameters", {}).get("migrate_to_chat_id"):
                migrated_id = str(res_json["parameters"]["migrate_to_chat_id"])
                logger.info(f"[send_telegram_notification] El chat {c_chat} fue migrado a supergrupo: {migrated_id}. Agregando a la lista de reintento...")
                if migrated_id not in candidate_chats:
                    candidate_chats.append(migrated_id)

            if response.status_code != 200 and "can't parse entities" in str(res_json.get("description", "")):
                logger.warning(f"[send_telegram_notification] Error de entidades en caption. Reintentando sin parse_mode para {c_chat}...")
                data.pop("parse_mode", None)
                if is_file_id:
                    response = await client.post(telegram_url, data=data)
                else:
                    with open(target_photo, "rb") as img_file:
                        files = {"photo": (target_photo.name, img_file, "image/png")}
                        response = await client.post(telegram_url, data=data, files=files)
                res_json = response.json()

            if response.status_code == 200 and res_json.get("ok"):
                sent_msg_id = res_json.get("result", {}).get("message_id")
                logger.info(f"[Telegram] Tarjeta PNG enviada exitosamente a chat={c_chat} (msg_id={sent_msg_id}, tipo={resolved_chat_type}).")
                if sent_msg_id:
                    try:
                        record_sent_card(
                            chat_id=str(c_chat),
                            message_id=sent_msg_id,
                            chat_type=resolved_chat_type
                        )
                    except Exception as ex_db:
                        logger.warning(f"No se pudo registrar la tarjeta en registro_tarjetas_enviadas: {ex_db}")

                photos = res_json.get("result", {}).get("photo", [])
                returned_file_id = photos[-1].get("file_id") if photos else (str(photo_path) if is_file_id else None)
                if trend_id and returned_file_id:
                    _trend_card_file_id_cache[trend_id] = returned_file_id
                return {"success": True, "result": res_json, "file_id": returned_file_id}

            last_error = res_json
        except Exception as e:
            logger.error(f"Fallo en la conexión con la API de Telegram para chat {c_chat}: {e}")
            last_error = {"ok": False, "error": str(e)}

    logger.error(f"Error en respuesta de Telegram API: {last_error}")
    return {"success": False, "error": last_error}


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
    message_id: Optional[int] = None,
    current_reply_markup: Optional[Dict[str, Any]] = None,
    user_id: Optional[Any] = None
) -> None:
    """1. Confirmación de Guardado (Post-Deep Dive):
    Almacena la tendencia en SQLite vinculada estrictamente al user_id y utiliza editMessageReplyMarkup
    para actualizar el teclado en línea de ese mensaje. El botón cambia de '⭐ Añadir a favoritos' a '✅ Guardado'
    y su callback_data queda inactivo ('NOOP') para evitar clics duplicados.
    """
    trend = _resolve_target_trend(trend_id)
    if not trend:
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="No se encontró la tendencia para guardar.", show_alert=True)
        return

    tid = trend["id"]
    target_uid = int(user_id) if user_id is not None and str(user_id).isdigit() else (int(chat_id) if str(chat_id).isdigit() else chat_id)
    mark_as_favorite(tid, message_id=message_id, user_id=target_uid)

    if callback_query_id:
        await answer_callback_query(callback_query_id, text="⭐ ¡Guardado en tus favoritos!", show_alert=False)

    if message_id:
        # Construir teclado con botón actualizado a "✅ Guardado"
        new_keyboard = None
        if current_reply_markup and "inline_keyboard" in current_reply_markup:
            import copy
            ik = copy.deepcopy(current_reply_markup["inline_keyboard"])
            for row in ik:
                for btn in row:
                    cb = btn.get("callback_data", "")
                    if cb.startswith("SAVE_TREND") or cb.startswith("save_favorite"):
                        btn["text"] = "✅ Guardado"
                        btn["callback_data"] = "NOOP"
            new_keyboard = {"inline_keyboard": ik}
        else:
            new_keyboard = {
                "inline_keyboard": [
                    [{"text": "✅ Guardado", "callback_data": "NOOP"}]
                ]
            }

        await edit_telegram_reply_markup(
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=new_keyboard
        )
    else:
        title = trend.get("title", "Tendencia")
        msg = (
            f"⭐ <b>Guardado en tus favoritos</b>\n\n"
            f"La tecnología <b>{title}</b> ha sido almacenada correctamente en tu lista de favoritos.\n\n"
            f"Puedes consultarla cuando desees con el comando <code>/favoritos</code>."
        )
        await send_telegram_message(
            text=msg,
            chat_id=chat_id,
            reply_markup={
                "inline_keyboard": [
                    [{"text": "📁 Ver favoritos", "callback_data": "VIEW_FAVS"}]
                ]
            }
        )


async def handle_view_favorites(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[Any] = None
) -> None:
    """1. Limpieza de Texto y 2. Botones de Título:
    Elimina por completo la impresión de enlaces web y URLs.
    El mensaje solo contiene un texto introductorio breve ('⭐ Tus tendencias guardadas:').
    Debajo genera un InlineKeyboardMarkup donde cada fila es '📌 {titulo}' con callback_data='VIEW_FAV_{trend_id}'.
    Al final se mantiene el botón '🗑️ Gestionar favoritos' (MANAGE_FAVS).
    """
    if callback_query_id:
        await answer_callback_query(callback_query_id)

    target_uid = int(user_id) if user_id is not None and str(user_id).isdigit() else (int(chat_id) if str(chat_id).isdigit() else chat_id)
    favs = get_favorites(user_id=target_uid)
    if not favs:
        empty_msg = (
            "📁 <b>Portafolio de Favoritos</b>\n\n"
            "Aún no tienes tecnologías guardadas en tus favoritos.\n\n"
            "Utiliza el botón <b>⭐ Guardar en favoritos</b> en tus tarjetas del radar "
            "o al profundizar para guardar las soluciones más relevantes."
        )
        empty_kb = {
            "inline_keyboard": [
                [
                    {"text": "🔙 Volver al radar", "callback_data": "CATALOG_GOTO:0"},
                    {"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR"}
                ]
            ]
        }
        if message_id:
            res = await edit_telegram_message_text(chat_id=chat_id, message_id=message_id, text=empty_msg, reply_markup=empty_kb)
            if not res.get("success"):
                await send_telegram_message(text=empty_msg, chat_id=chat_id, reply_markup=empty_kb)
        else:
            await send_telegram_message(text=empty_msg, chat_id=chat_id, reply_markup=empty_kb)
        return

    # 1. Limpieza de Texto: Solo un texto introductorio breve sin URLs ni enlaces crudos
    text = "⭐ <b>Tus tendencias guardadas:</b>"

    # 2. Botones de Título: Una fila por cada tendencia con "📌 {titulo}"
    buttons = []
    for f in favs:
        title = f.get("title", "Tendencia")
        buttons.append([
            {"text": f"📌 {title}", "callback_data": f"VIEW_FAV_{f['id']}"}
        ])

    # 3. Respetar Menú de Gestión: Mantener "🗑️ Gestionar favoritos" intacto al final
    buttons.append([
        {"text": "🗑️ Gestionar favoritos", "callback_data": "MANAGE_FAVS"}
    ])
    # 4. Navegación bidireccional: Retorno garantizado
    buttons.append([
        {"text": "🔙 Volver al radar", "callback_data": "CATALOG_GOTO:0"},
        {"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR"}
    ])

    reply_markup = {"inline_keyboard": buttons}

    if message_id:
        res = await edit_telegram_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=reply_markup
        )
        if not res.get("success"):
            await send_telegram_message(text=text, chat_id=chat_id, reply_markup=reply_markup)
    else:
        await send_telegram_message(text=text, chat_id=chat_id, reply_markup=reply_markup)


async def handle_manage_favorites(
    chat_id: str,
    message_id: int,
    callback_query_id: Optional[str] = None,
    user_id: Optional[Any] = None
) -> None:
    """3. Modo de Eliminación:
    Edita el mensaje y despliega un InlineKeyboardMarkup donde cada fila es un botón
    con el nombre de la tendencia ('❌ {Titulo_Tendencia}') y callback_data='REMOVE_FAV_{trend_id}'.
    Incluye un botón '⬅️ Volver' al final para regresar a la vista de lectura.
    """
    if callback_query_id:
        await answer_callback_query(callback_query_id)

    target_uid = int(user_id) if user_id is not None and str(user_id).isdigit() else (int(chat_id) if str(chat_id).isdigit() else chat_id)
    favs = get_favorites(user_id=target_uid)
    if not favs:
        text = (
            "🗑️ <b>Gestión de Favoritos</b>\n\n"
            "No tienes tecnologías guardadas para eliminar."
        )
        buttons = [
            [{"text": "⬅️ Volver", "callback_data": "VIEW_FAVS"}]
        ]
        await edit_telegram_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup={"inline_keyboard": buttons}
        )
        return

    buttons = []
    for f in favs:
        title = f.get("title", "Tendencia")
        btn_text = f"❌ {title}"
        buttons.append([
            {"text": btn_text, "callback_data": f"REMOVE_FAV_{f['id']}"}
        ])

    buttons.append([
        {"text": "⬅️ Volver", "callback_data": "VIEW_FAVS"}
    ])

    text = (
        "🗑️ <b>Gestión de Favoritos (Modo Eliminación)</b>\n\n"
        "Toca sobre cualquier tecnología para retirarla de tu lista.\n"
        "Pulsa <b>⬅️ Volver</b> para regresar a la vista de lectura:"
    )

    await edit_telegram_message_text(
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        reply_markup={"inline_keyboard": buttons}
    )


async def handle_remove_favorite(
    chat_id: str,
    trend_id: int,
    callback_query_id: Optional[str] = None,
    message_id: Optional[int] = None,
    user_id: Optional[Any] = None
) -> None:
    """4. Bucle de Eliminación Dinámica:
    Tras ejecutar el DELETE en SQLite filtrando por user_id, actualiza instantáneamente el mensaje actual (Modo Eliminación)
    para que el botón de la tendencia recién borrada desaparezca, permitiendo borrar varios elementos
    sin salir del menú.
    """
    target_uid = int(user_id) if user_id is not None and str(user_id).isdigit() else (int(chat_id) if str(chat_id).isdigit() else chat_id)
    success = remove_favorite(user_id=target_uid, trend_id=trend_id)

    if callback_query_id:
        if success:
            await answer_callback_query(callback_query_id, text="❌ Eliminado de favoritos.")
        else:
            await answer_callback_query(callback_query_id, text="No se encontró o ya fue eliminado.", show_alert=True)

    # Actualizar instantáneamente el menú en Modo Eliminación
    favs = get_favorites(user_id=target_uid)
    if message_id:
        if not favs:
            text = (
                "🗑️ <b>Gestión de Favoritos</b>\n\n"
                "✅ <i>Todas las tecnologías seleccionadas han sido eliminadas.</i>\n\n"
                "Tu portafolio de favoritos está vacío."
            )
            buttons = [
                [{"text": "⬅️ Volver", "callback_data": "VIEW_FAVS"}]
            ]
            await edit_telegram_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup={"inline_keyboard": buttons}
            )
        else:
            buttons = []
            for f in favs:
                title = f.get("title", "Tendencia")
                btn_text = f"❌ {title}"
                buttons.append([
                    {"text": btn_text, "callback_data": f"REMOVE_FAV_{f['id']}"}
                ])
            buttons.append([
                {"text": "⬅️ Volver", "callback_data": "VIEW_FAVS"}
            ])

            text = (
                "🗑️ <b>Gestión de Favoritos (Modo Eliminación)</b>\n\n"
                "✅ <i>Elemento eliminado.</i> Toca otra tecnología para retirarla, o pulsa <b>⬅️ Volver</b>:"
            )
            await edit_telegram_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                reply_markup={"inline_keyboard": buttons}
            )
    else:
        await send_telegram_message(
            text="❌ La tecnología ha sido eliminada de tus favoritos.",
            chat_id=chat_id
        )


async def handle_view_favorite_card(
    chat_id: str,
    fav_id: Optional[int] = None,
    callback_query_id: Optional[str] = None,
    user_id: Optional[Any] = None
) -> None:
    """4. Renderizado Inmortal:
    Consulta los datos completos de esa tendencia en SQLite y vuelve a enviar la tarjeta visual original
    (o reporte detallado) en un mensaje nuevo, asegurando la lectura aunque el mensaje original haya
    sido eliminado por el TTL de 7 días.
    """
    if fav_id is None:
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="ID de tendencia no válido.", show_alert=True)
        return

    target_uid = int(user_id) if user_id is not None and str(user_id).isdigit() else (int(chat_id) if str(chat_id).isdigit() else chat_id)
    trend = get_favorite_or_trend(fav_id, user_id=target_uid)
    if not trend:
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="No se encontró la tendencia en tus favoritos.", show_alert=True)
        await send_telegram_message(
            text="⚠️ No se encontraron datos para la tendencia seleccionada en tus favoritos.",
            chat_id=chat_id
        )
        return

    title = trend.get("title", "Tendencia")
    if callback_query_id:
        await answer_callback_query(callback_query_id, text=f"📌 Recuperando {title}...")

    card_data = trend.get("card_data")
    buttons = [
        [
            {"text": "🔍 Profundizar datos", "callback_data": f"DEEP_DIVE:{trend.get('id', fav_id)}"}
        ],
        [
            {"text": "📁 Volver a favoritos", "callback_data": "VIEW_FAVS"},
            {"text": "🏠 Catálogo de hoy", "callback_data": "CATALOG_GOTO:0"}
        ]
    ]
    reply_markup = {"inline_keyboard": buttons}

    # Intentar renderizar tarjeta visual PNG inmortal con Playwright si hay card_data
    if card_data and isinstance(card_data, dict):
        try:
            from app.visual_engine import create_png_card
            temp_card_path = settings.BASE_DIR / f"temp_fav_{fav_id}.png"
            await create_png_card(data=card_data, output_path=temp_card_path)

            caption = (
                f"📌 <b>{title}</b>\n\n"
                f"<i>Tecnología recuperada de tu portafolio de favoritos.</i>"
            )
            res = await send_telegram_notification(
                photo_path=temp_card_path,
                caption=caption,
                chat_id=chat_id,
                reply_markup=reply_markup,
                trend_id=fav_id
            )
            if res.get("success"):
                return
        except Exception as e_card:
            logger.warning(f"[handle_view_favorite_card] Falló renderizado de tarjeta ({e_card}), procediendo con reporte.")

    # Si no hay card_data estructurada o falló el renderizado visual, enviar ficha completa en mensaje nuevo
    category = trend.get("category") or "Tecnología B2B"
    source = trend.get("source") or "Radar B2B"
    score = trend.get("score") or "95.0"
    url = trend.get("url") or ""

    lines = [
        f"📌 <b>{title}</b>\n",
        f"• <b>Categoría:</b> {category}",
        f"• <b>Fuente:</b> {source}",
        f"• <b>Score de Relevancia:</b> {score}",
    ]
    if url:
        lines.append(f"• <b>Fuente original:</b> <a href='{url}'>{url}</a>")

    lines.append("\n<i>Tecnología recuperada de tu portafolio de favoritos.</i>")
    text = "\n".join(lines)

    await send_telegram_message(
        text=text,
        chat_id=chat_id,
        reply_markup=reply_markup
    )


async def handle_load_favorite(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    fav_id: Optional[int] = None
) -> None:
    """Compatibilidad: delega en handle_view_favorite_card para garantizar la visualización inmortal."""
    await handle_view_favorite_card(chat_id=chat_id, fav_id=fav_id, callback_query_id=callback_query_id)


async def handle_get_chart(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None,
    message_id: Optional[int] = None,
    current_reply_markup: Optional[Dict[str, Any]] = None,
    to_original: bool = False
) -> None:
    """Procesa la acción de alternancia (toggle) de la gráfica en el chat privado (DM).
    REGLA: ELIMINA el uso de sendPhoto y utiliza obligatoriamente editMessageMedia
    para actualizar la foto dentro del mismo globo de mensaje (cero spam).
    - Estado Gráfica: el botón se actualiza a '📍 Tendencia original' (preservando los demás botones).
    - Estado Original: el botón se actualiza a '📈 Ver gráfica' (preservando los demás botones).
    """
    # Feedback visual instantáneo para el usuario
    asyncio.create_task(send_chat_action(action="upload_photo", chat_id=chat_id))

    from app.visual_engine import create_chart_png_card, create_png_card
    from app.database import get_trend_by_id, get_recent_sent_trends, get_last_sent_card_message

    target_msg_id = message_id or get_last_sent_card_message(chat_id)

    trend = None
    if trend_id is not None:
        trend = get_trend_by_id(trend_id)
    if not trend:
        recent = get_recent_sent_trends(limit=1)
        if recent:
            trend = get_trend_by_id(recent[0]["id"])
            if trend and trend_id is None:
                trend_id = trend["id"]

    if to_original:
        # Alternar a la tarjeta original de la tendencia
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="📍 Mostrando tendencia original...")

        photo_to_use: Path | str = ""
        cached_file_id = _trend_card_file_id_cache.get(trend_id)
        if cached_file_id:
            photo_to_use = cached_file_id
        else:
            temp_card_path = settings.BASE_DIR / f"temp_trend_{trend_id}.png"
            if temp_card_path.exists():
                photo_to_use = temp_card_path
            elif (settings.BASE_DIR / "temp_card.png").exists() and (not trend or trend.get("id") == trend_id):
                photo_to_use = settings.BASE_DIR / "temp_card.png"
            elif trend and trend.get("card_data"):
                photo_to_use = await create_png_card(data=trend["card_data"], output_path=temp_card_path)
            else:
                photo_to_use = settings.BASE_DIR / "temp_card.png"

        new_kb = update_dm_keyboard_chart_toggle(
            current_reply_markup=current_reply_markup,
            showing_chart=False,
            trend_id=trend_id
        )

        if target_msg_id:
            res = await edit_telegram_media(
                chat_id=chat_id,
                message_id=target_msg_id,
                photo_path=photo_to_use,
                reply_markup=new_kb
            )
            if res.get("file_id") and trend_id:
                _trend_card_file_id_cache[trend_id] = res["file_id"]
    else:
        # Alternar a la gráfica de tendencias
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="📈 Mostrando gráfica de tendencias...")

        photo_to_use = ""
        cached_chart_id = _chart_file_id_cache.get(f"chart_{trend_id}") or _chart_file_id_cache.get("latest")
        if cached_chart_id:
            photo_to_use = cached_chart_id
        else:
            chart_target = settings.BASE_DIR / "temp_chart.png"
            try:
                await create_chart_png_card(output_path=chart_target)
                photo_to_use = chart_target
            except Exception as e_chart:
                logger.error(f"[handle_get_chart] Error renderizando gráfica: {e_chart}")
                if callback_query_id:
                    await answer_callback_query(callback_query_id, text="⚠️ No se pudo renderizar la gráfica.", show_alert=True)
                return

        new_kb = update_dm_keyboard_chart_toggle(
            current_reply_markup=current_reply_markup,
            showing_chart=True,
            trend_id=trend_id
        )

        if target_msg_id:
            res = await edit_telegram_media(
                chat_id=chat_id,
                message_id=target_msg_id,
                photo_path=photo_to_use,
                reply_markup=new_kb
            )
            if res.get("file_id"):
                if trend_id:
                    _chart_file_id_cache[f"chart_{trend_id}"] = res["file_id"]
                _chart_file_id_cache["latest"] = res["file_id"]


async def handle_get_stack(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None
) -> None:
    """Envía el desglose del stack técnico y arquitectura sugerida."""
    if callback_query_id:
        await answer_callback_query(callback_query_id, text="🛠️ Consultando stack técnico...")

    trend = _resolve_target_trend(trend_id)
    title = trend.get("title", "Solución B2B") if trend else "Solución B2B"
    card_data = (trend.get("card_data") or {}) if trend else {}
    stack_list = card_data.get("stack_list") or []

    if isinstance(stack_list, list) and stack_list:
        stack_items = []
        for s in stack_list:
            if isinstance(s, dict):
                stack_items.append(f"• <b>{s.get('name', 'Tecnología')}</b>: {s.get('desc', 'Componente clave')}")
            else:
                stack_items.append(f"• <b>{s}</b>")
        stack_text = "\n".join(stack_items)
    else:
        stack_text = (
            "• <b>APIs RESTful & Webhooks</b>: Intercambio e integración de datos en tiempo real.\n"
            "• <b>Python / FastAPI</b>: Lógica de negocio y backend escalable de alta concurrencia.\n"
            "• <b>PostgreSQL / Redis</b>: Base de datos relacional y caché de alta velocidad.\n"
            "• <b>Docker & Cloud Native</b>: Arquitectura contenerizada desacoplada."
        )

    msg = (
        f"🛠️ <b>Stack Técnico & Arquitectura Sugerida</b>\n"
        f"📌 <b>Solución:</b> {title}\n\n"
        f"{stack_text}\n\n"
        f"<i>Arquitectura modular desacoplada diseñada para rápida integración B2B.</i>"
    )

    tid = trend.get("id") if trend else trend_id
    reply_markup = build_interactive_keyboard(trend_id=tid)

    return await send_telegram_message(
        text=msg,
        chat_id=chat_id,
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def handle_toggle_chart(
    chat_id: str,
    message_id: int,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None,
    to_original: bool = False
) -> None:
    """Alterna dinámicamente entre la tarjeta visual principal y la gráfica de tendencias en el grupo público.
    Utiliza editMessageMedia para editar in-situ el mensaje existente (cero spam).
    """
    from app.visual_engine import create_chart_png_card, create_png_card
    from app.database import get_trend_by_id, get_recent_sent_trends

    trend = None
    if trend_id is not None:
        trend = get_trend_by_id(trend_id)
    if not trend:
        recent = get_recent_sent_trends(limit=1)
        if recent:
            trend = get_trend_by_id(recent[0]["id"])
            if trend and trend_id is None:
                trend_id = trend["id"]

    if to_original:
        # Volver a la tarjeta original de la tendencia
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="📍 Mostrando tendencia original...")

        photo_to_use: Path | str = ""
        cached_file_id = _trend_card_file_id_cache.get(trend_id)
        if cached_file_id:
            photo_to_use = cached_file_id
        else:
            temp_card_path = settings.BASE_DIR / f"temp_trend_{trend_id}.png"
            if temp_card_path.exists():
                photo_to_use = temp_card_path
            elif (settings.BASE_DIR / "temp_group_card.png").exists() and trend and trend.get("id") == trend_id:
                photo_to_use = settings.BASE_DIR / "temp_group_card.png"
            elif trend and trend.get("card_data"):
                photo_to_use = await create_png_card(data=trend["card_data"], output_path=temp_card_path)
            else:
                photo_to_use = settings.BASE_DIR / "temp_group_card.png"

        new_kb = build_group_keyboard(trend_id=trend_id, showing_chart=False)
        res = await edit_telegram_media(
            chat_id=chat_id,
            message_id=message_id,
            photo_path=photo_to_use,
            reply_markup=new_kb
        )
        if res.get("file_id") and trend_id:
            _trend_card_file_id_cache[trend_id] = res["file_id"]
    else:
        # Alternar a la gráfica de tendencias
        if callback_query_id:
            await answer_callback_query(callback_query_id, text="📈 Mostrando gráfica de tendencias...")

        photo_to_use = ""
        cached_chart_id = _chart_file_id_cache.get(f"chart_{trend_id}") or _chart_file_id_cache.get("latest")
        if cached_chart_id:
            photo_to_use = cached_chart_id
        else:
            chart_target = settings.BASE_DIR / "temp_chart.png"
            try:
                await create_chart_png_card(output_path=chart_target)
                photo_to_use = chart_target
            except Exception as e_chart:
                logger.error(f"[handle_toggle_chart] Error renderizando gráfica: {e_chart}")
                if callback_query_id:
                    await answer_callback_query(callback_query_id, text="⚠️ No se pudo renderizar la gráfica.", show_alert=True)
                return

        new_kb = build_group_keyboard(trend_id=trend_id, showing_chart=True)
        res = await edit_telegram_media(
            chat_id=chat_id,
            message_id=message_id,
            photo_path=photo_to_use,
            reply_markup=new_kb
        )
        if res.get("file_id"):
            _chart_file_id_cache[f"chart_{trend_id}"] = res["file_id"]
            _chart_file_id_cache["latest"] = res["file_id"]


async def handle_deep_dive(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    trend_id: Optional[int] = None
) -> None:
    """4. '🔍 Profundizar datos': Genera reporte técnico y comercial denso y exhaustivo con Gemma."""
    if callback_query_id:
        await answer_callback_query(callback_query_id, text="🔍 Generando reporte técnico y comercial...")

    # Feedback visual instantáneo para el usuario
    asyncio.create_task(send_chat_action(action="typing", chat_id=chat_id))

    trend = _resolve_target_trend(trend_id)
    if not trend:
        await send_telegram_message(
            text="⚠️ No se encontraron datos para generar el reporte profundo.",
            chat_id=chat_id
        )
        return

    from app.database import get_user_zone, get_user_industry
    user_zone = get_user_zone(chat_id)
    user_ind = get_user_industry(chat_id)
    effective_zone = str(user_zone or trend.get("geo_region") or "Global")
    effective_ind = str(user_ind or trend.get("target_industry") or trend.get("category") or "TI & Software B2B")
    if user_zone:
        trend["geo_region"] = user_zone
    if user_ind:
        trend["target_industry"] = user_ind

    from app.llm_service import generate_deep_dive_report
    report = await generate_deep_dive_report(
        trend_data=trend,
        zona_preferida=effective_zone,
        user_industry=effective_ind
    )
    target_trend_id = trend.get("id") or trend_id
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "⭐ Guardar en favoritos", "callback_data": f"SAVE_TREND:{target_trend_id}"}
            ],
            [
                {"text": "🔙 Volver a la tarjeta", "callback_data": "CATALOG_GOTO:0"},
                {"text": "📁 Mis favoritos", "callback_data": "VIEW_FAVS"}
            ],
            [
                {"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR"},
                {"text": "⚙️ Configuración", "callback_data": "RESET_CONFIG"}
            ]
        ]
    }

    await send_telegram_message(
        text=report,
        chat_id=chat_id,
        parse_mode="HTML",
        reply_markup=reply_markup
    )


async def handle_zone_command(chat_id: str) -> None:
    """3. Menú de Zona en Telegram: Despliega un teclado interactivo con opciones de región."""
    current_zone = get_user_zone(chat_id)
    zone_options = [
        ("🌎 Global", "Global"),
        ("🇲🇽 México", "Mexico"),
        ("🇺🇸 Estados Unidos", "US"),
        ("🇪🇺 Europa", "Europa"),
        ("🇨🇴 Colombia", "Colombia")
    ]

    inline_keyboard = []
    for label, key in zone_options:
        is_selected = " ✓" if current_zone == key or (key == "Mexico" and current_zone == "México") or (key == "US" and current_zone == "Estados Unidos") else ""
        inline_keyboard.append([
            {"text": f"{label}{is_selected}", "callback_data": f"SET_ZONE:{key}"}
        ])

    text = (
        "🌍 <b>Configuración de Zona Geográfica</b>\n\n"
        f"Tu mercado prioritario actual es: <b>{current_zone}</b>\n\n"
        "Selecciona una región para enfocar el análisis de tendencias, volumen de búsqueda y viabilidad comercial:"
    )

    await send_telegram_message(
        text=text,
        chat_id=chat_id,
        reply_markup={"inline_keyboard": inline_keyboard}
    )


async def handle_set_zone(
    chat_id: str,
    callback_query_id: Optional[str] = None,
    zone_key: str = "Global"
) -> None:
    """Almacena la preferencia de zona en SQLite y confirma al usuario."""
    zone_names = {
        "Global": "🌎 Global",
        "Mexico": "🇲🇽 México",
        "México": "🇲🇽 México",
        "US": "🇺🇸 Estados Unidos",
        "Estados Unidos": "🇺🇸 Estados Unidos",
        "Europa": "🇪🇺 Europa",
        "Colombia": "🇨🇴 Colombia"
    }
    display_name = zone_names.get(zone_key, zone_key)
    set_user_zone(chat_id=chat_id, zone=zone_key)

    if callback_query_id:
        await answer_callback_query(callback_query_id, text=f"✅ Zona configurada: {display_name}")

    msg = (
        f"✅ <b>Preferencia de Zona Actualizada</b>\n\n"
        f"Mercado configurado: <b>{display_name}</b>\n\n"
        "A partir de ahora, los radares de tendencias y los reportes de profundización "
        f"evaluarán prioritariamente el impacto y la viabilidad para <b>{display_name}</b>."
    )
    await send_telegram_message(text=msg, chat_id=chat_id)


# Cache en memoria de tendencias de catálogo para navegación instantánea
_cached_catalog_trends: List[Dict[str, Any]] = []
_last_catalog_cache_time: float = 0.0
_recent_callbacks: Dict[str, float] = {}

def get_cached_catalog_trends() -> List[Dict[str, Any]]:
    """Devuelve las 5 tendencias del catálogo desde memoria si están frescas (< 60s)."""
    global _cached_catalog_trends, _last_catalog_cache_time
    now = time.time()
    if not _cached_catalog_trends or (now - _last_catalog_cache_time) > 60:
        from app.database import get_daily_catalog_trends
        _cached_catalog_trends = get_daily_catalog_trends(limit=5)
        _last_catalog_cache_time = now
    return _cached_catalog_trends

def set_cached_catalog_trends(trends: List[Dict[str, Any]]) -> None:
    """Actualiza la caché en memoria del catálogo interactivo de tendencias."""
    global _cached_catalog_trends, _last_catalog_cache_time
    _cached_catalog_trends = list(trends)
    _last_catalog_cache_time = time.time()

def is_duplicate_callback(cb_key: str, window: float = 0.6) -> bool:
    """Evita ejecuciones concurrentes o doble clics rápidos en Telegram."""
    global _recent_callbacks
    now = time.time()
    last = _recent_callbacks.get(cb_key, 0.0)
    if (now - last) < window:
        return True
    _recent_callbacks[cb_key] = now
    # Limpieza periódica
    if len(_recent_callbacks) > 100:
        _recent_callbacks = {k: v for k, v in _recent_callbacks.items() if (now - v) < 5.0}
    return False

WELCOME_INTRO_MSG = (
    "👋 ¡Hola! Bienvenido a tu espacio analítico privado. Para no saturar el grupo público, aquí te entregaré reportes detallados y alertas personalizadas.\n\n"
    "Para que la información sea exacta, vamos a configurar tu radar."
)
STEP1_ZONE_MSG = "🌎 ¿De qué país o región tecnológica te interesa recibir tendencias? (Ej. China, Silicon Valley, Europa, Global)"


async def open_private_chat(
    user_id: str | int,
    payload: Dict[str, Any],
    callback_query_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Abre una conversación privada (DM) con el usuario y despacha la acción a la Rama B.
    Si el usuario no ha iniciado chat con el bot, le notifica mediante alert visual en Telegram.
    """
    uid_str = str(user_id)
    try:
        from app.rama_b import process_private_action
        res = await process_private_action(uid_str, payload)
        
        # Verificar si falló el envío (ej: usuario no ha iniciado el bot en privado)
        if isinstance(res, dict) and not res.get("success"):
            err_desc = str(res.get("error", {}))
            logger.warning(f"[open_private_chat] Telegram rechazó mensaje a {uid_str}: {err_desc}")
            if callback_query_id:
                bot_usr = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
                await answer_callback_query(
                    callback_query_id,
                    text=f"⚠️ Para recibir la información en privado, primero inicia chat con el bot aquí: @{bot_usr}",
                    show_alert=True
                )
            return res
        
        # Si se envió con éxito, confirmar en el botón
        if callback_query_id:
            await answer_callback_query(
                callback_query_id,
                text="✅ ¡Te envié los detalles a tu chat privado!",
                show_alert=False
            )
        return res if isinstance(res, dict) else {"success": True}

    except Exception as exc:
        logger.exception(f"[open_private_chat] Error despachando a {uid_str}: {exc}")
        if callback_query_id:
            bot_usr = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
            await answer_callback_query(
                callback_query_id,
                text=f"⚠️ Abre chat privado con @{bot_usr} para recibir la información.",
                show_alert=True
            )
        return {"success": False, "error": str(exc)}


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

        # Extraer acción y trend_id del callback_data
        parts = data.split(":")
        action = parts[0]
        trend_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        chat_type = msg_obj.get("chat", {}).get("type", "private")

        # Extraer ID del usuario llamante (query.from_user.id)
        from_user = cq.get("from", {})
        caller_user_id = from_user.get("id") or (int(user_chat_id) if user_chat_id.isdigit() else user_chat_id)
        logger.info(f"[Telegram Bot] CallbackQuery recibido: '{data}' de user_id={caller_user_id} (chat={user_chat_id}, tipo={chat_type})")

        # 0. Agradecimiento no-bloqueante inmediato para apagar el spinner en el cliente de Telegram al instante
        if not action.startswith("SET_ZONE") and action != "RESET_CONFIG":
            asyncio.create_task(answer_callback_query(cb_id))

        # Manejo de CATALOG_INFO:{idx}
        if action == "CATALOG_INFO":
            info_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            asyncio.create_task(answer_callback_query(cb_id, text=f"📍 Tendencia {info_idx + 1}. Usa ◀️ y ▶️ para explorar el catálogo."))
            return

        # Manejo de CATALOG_NAV:prev:{idx} o CATALOG_NAV:next:{idx}
        if action == "CATALOG_NAV":
            # Debounce de doble clic rápido
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return

            direction = parts[1] if len(parts) > 1 else "next"
            curr_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            trends = get_cached_catalog_trends()
            if not trends:
                return
            total_items = len(trends)
            new_idx = (curr_idx + 1) % total_items if direction == "next" else (curr_idx - 1) % total_items
            target_trend = trends[new_idx]
            target_tid = target_trend["id"]

            cache_key = f"trend_{target_tid}"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / f"temp_trend_{target_tid}.png"
                if not target_png.exists():
                    card_dict = target_trend.get("card_data") or {}
                    if card_dict:
                        from app.visual_engine import create_png_card
                        await create_png_card(data=card_dict, output_path=target_png)
                photo_to_use = target_png if target_png.exists() else (settings.BASE_DIR / "temp_card.png")

            if chat_type == "private":
                kb = build_interactive_keyboard(trend_id=target_tid, current_index=new_idx, total_items=total_items)
            else:
                kb = build_catalog_keyboard(current_index=new_idx, total_items=total_items, trend_id=target_tid)
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return

        # Manejo de CATALOG_GOTO:{idx} (Retorno in-situ al catálogo / Menú Principal 🏠)
        if action == "CATALOG_GOTO":
            asyncio.create_task(answer_callback_query(cb_id))
            
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return

            target_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            trends = get_cached_catalog_trends()
            if not trends:
                return
            total_items = len(trends)
            target_idx = target_idx % total_items
            target_trend = trends[target_idx]
            target_tid = target_trend["id"]

            cache_key = f"trend_{target_tid}"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / f"temp_trend_{target_tid}.png"
                if not target_png.exists():
                    card_dict = target_trend.get("card_data") or {}
                    if card_dict:
                        from app.visual_engine import create_png_card
                        await create_png_card(data=card_dict, output_path=target_png)
                photo_to_use = target_png if target_png.exists() else (settings.BASE_DIR / "temp_card.png")

            if chat_type == "private":
                kb = build_interactive_keyboard(trend_id=target_tid, current_index=target_idx, total_items=total_items)
            else:
                kb = build_catalog_keyboard(current_index=target_idx, total_items=total_items, trend_id=target_tid)
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return

        # Manejo de DEMANDA_INFO:{idx}
        if action == "DEMANDA_INFO":
            info_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            asyncio.create_task(answer_callback_query(cb_id, text=f"🏢 Empresa demandante {info_idx + 1}. Usa ◀️ y ▶️ para comparar requerimientos."))
            return

        # Manejo de DEMANDA_SCOPE:{idx}:{return_trend_idx} (Redirige a Rama B - Chat Privado)
        if action == "DEMANDA_SCOPE":
            info_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            ret_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

            payload = {"action": "DEMANDA_SCOPE", "idx": info_idx, "return_idx": ret_idx}
            await open_private_chat(caller_user_id, payload, callback_query_id=cb_id)
            return

        # Manejo de DEMANDA_QUOTE:{idx}:{return_trend_idx} (Redirige a Rama B - Chat Privado)
        if action == "DEMANDA_QUOTE":
            info_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            ret_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

            payload = {"action": "DEMANDA_QUOTE", "idx": info_idx, "return_idx": ret_idx}
            await open_private_chat(caller_user_id, payload, callback_query_id=cb_id)
            return

        # Manejo de NAV_DEMANDA_PAGE:{prev/next}:{curr_idx}:{return_trend_idx} (Carrusel de Empresas Demandantes)
        if action == "NAV_DEMANDA_PAGE":
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return
            asyncio.create_task(answer_callback_query(cb_id))

            direction = parts[1] if len(parts) > 1 else "next"
            curr_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            ret_idx = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

            from app.b2b_demand import get_all_b2b_demand_companies, get_b2b_demand_by_index
            companies = get_all_b2b_demand_companies()
            total_items = len(companies)
            if direction == "next":
                new_idx = (curr_idx + 1) % total_items
            elif direction == "prev":
                new_idx = (curr_idx - 1) % total_items
            else:
                new_idx = curr_idx % total_items

            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            demand_data = get_b2b_demand_by_index(new_idx)
            cache_key = f"demand_b2b_{new_idx}_{today_str}"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / f"temp_demand_{new_idx}_{today_str}.png"
                if not target_png.exists():
                    from app.visual_engine import create_b2b_demand_png_card
                    await create_b2b_demand_png_card(output_path=target_png, data=demand_data)
                photo_to_use = target_png

            kb = build_demand_keyboard(
                current_index=new_idx,
                total_items=total_items,
                return_index=ret_idx,
                company_linkedin_url=demand_data.get("linkedin_company_url"),
                company_web_url=demand_data.get("contact_web"),
                linkedin_status=demand_data.get("linkedin_status", "active")
            )
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return

        # Manejo de NAV_DEMANDA:{return_idx} (Entrada in-situ a Catálogo de Empresas Demandantes)
        if action == "NAV_DEMANDA":
            asyncio.create_task(answer_callback_query(cb_id))
            
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return

            ret_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            from app.b2b_demand import get_all_b2b_demand_companies, get_b2b_demand_by_index
            companies = get_all_b2b_demand_companies()
            total_items = len(companies)

            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            demand_data = get_b2b_demand_by_index(0)
            cache_key = f"demand_b2b_0_{today_str}"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / f"temp_demand_0_{today_str}.png"
                if not target_png.exists():
                    from app.visual_engine import create_b2b_demand_png_card
                    await create_b2b_demand_png_card(output_path=target_png, data=demand_data)
                photo_to_use = target_png

            kb = build_demand_keyboard(
                current_index=0,
                total_items=total_items,
                return_index=ret_idx,
                company_linkedin_url=demand_data.get("linkedin_company_url"),
                company_web_url=demand_data.get("contact_web"),
                linkedin_status=demand_data.get("linkedin_status", "active")
            )
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return

        # Manejo de EVENTOS_INFO:{idx}
        if action == "EVENTOS_INFO":
            info_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            asyncio.create_task(answer_callback_query(cb_id, text=f"📅 Evento CDMX {info_idx + 1}. Usa ◀️ y ▶️ para explorar el calendario."))
            return

        # Manejo de EVENTOS_DETAILS:{idx}:{return_trend_idx} (Ficha Logística y de Registro)
        if action == "EVENTOS_DETAILS":
            info_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            ret_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            asyncio.create_task(answer_callback_query(cb_id, text="📋 Abriendo logística y detalles de asistencia..."))

            from app.events_cdmx import get_events_cdmx_by_index
            evt_info = get_events_cdmx_by_index(info_idx)
            info_text = evt_info.get("info_summary") or "Detalles no disponibles."

            back_kb = {
                "inline_keyboard": [
                    [
                        {"text": "🎟️ Enlace Directo de Registro", "url": evt_info.get("registration_url", "https://lu.ma/mxtw")}
                    ],
                    [
                        {"text": "🔙 Volver al Evento", "callback_data": f"NAV_EVENTOS_PAGE:curr:{info_idx}:{ret_idx}"},
                        {"text": "🏠 Inicio", "callback_data": f"CATALOG_GOTO:{ret_idx}"}
                    ]
                ]
            }
            await send_telegram_message(
                text=info_text,
                chat_id=user_chat_id,
                parse_mode="HTML",
                reply_markup=back_kb
            )
            return

        # Manejo de NAV_EVENTOS_PAGE:{prev/next}:{curr_idx}:{return_trend_idx} (Carrusel de Calendario de Eventos)
        if action == "NAV_EVENTOS_PAGE":
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return
            asyncio.create_task(answer_callback_query(cb_id))

            direction = parts[1] if len(parts) > 1 else "next"
            curr_idx = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
            ret_idx = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0

            from app.events_cdmx import get_all_events_cdmx, get_events_cdmx_by_index
            events_list = get_all_events_cdmx()
            total_items = len(events_list)
            if direction == "next":
                new_idx = (curr_idx + 1) % total_items
            elif direction == "prev":
                new_idx = (curr_idx - 1) % total_items
            else:
                new_idx = curr_idx % total_items

            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            events_data = get_events_cdmx_by_index(new_idx)
            cache_key = f"events_cdmx_{new_idx}_{today_str}"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / f"temp_events_{new_idx}_{today_str}.png"
                if not target_png.exists():
                    from app.visual_engine import create_events_cdmx_png_card
                    await create_events_cdmx_png_card(output_path=target_png, data=events_data)
                photo_to_use = target_png

            kb = build_events_keyboard(
                current_index=new_idx,
                total_items=total_items,
                return_index=ret_idx,
                registration_url=events_data.get("registration_url")
            )
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return

        # Manejo de NAV_EVENTOS:{return_idx} (Entrada in-situ a Calendario de Eventos CDMX)
        if action == "NAV_EVENTOS":
            asyncio.create_task(answer_callback_query(cb_id))
            
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return

            ret_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            from app.events_cdmx import get_all_events_cdmx, get_events_cdmx_by_index
            events_list = get_all_events_cdmx()
            total_items = len(events_list)

            today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
            events_data = get_events_cdmx_by_index(0)
            cache_key = f"events_cdmx_0_{today_str}"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / f"temp_events_0_{today_str}.png"
                if not target_png.exists():
                    from app.visual_engine import create_events_cdmx_png_card
                    await create_events_cdmx_png_card(output_path=target_png, data=events_data)
                photo_to_use = target_png

            kb = build_events_keyboard(
                current_index=0,
                total_items=total_items,
                return_index=ret_idx,
                registration_url=events_data.get("registration_url")
            )
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return

        # Manejo de CATALOG_CHART:{idx}:{trend_id} (Edición in-situ a Gráfica de Tracción)
        if action == "CATALOG_CHART":
            asyncio.create_task(answer_callback_query(cb_id))
            
            debounce_key = f"{user_chat_id}:{orig_msg_id}:{data}"
            if is_duplicate_callback(debounce_key):
                return

            ret_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0

            cache_key = "chart_traction"
            cached_file_id = get_catalog_cached_file_id(cache_key)

            if cached_file_id:
                photo_to_use = cached_file_id
            else:
                target_png = settings.BASE_DIR / "temp_chart.png"
                if not target_png.exists():
                    from app.visual_engine import create_chart_png_card
                    await create_chart_png_card(output_path=target_png)
                photo_to_use = target_png

            kb = build_chart_keyboard(return_index=ret_idx)
            res = await edit_telegram_media(chat_id=user_chat_id, message_id=orig_msg_id, photo_path=photo_to_use, reply_markup=kb)
            if res.get("file_id"):
                set_catalog_cached_file_id(cache_key, res["file_id"])
            return



        # Manejo de RESET_CONFIG
        if action == "RESET_CONFIG":
            from app.database import reset_user_config
            reset_user_config(user_chat_id)
            asyncio.create_task(answer_callback_query(cb_id, text="⚙️ Configuración reiniciada."))
            await send_telegram_message(text=WELCOME_INTRO_MSG, chat_id=user_chat_id)
            await send_telegram_message(text=STEP1_ZONE_MSG, chat_id=user_chat_id)
            return

        # Manejo de SET_ZONE:{key}
        if action == "SET_ZONE" or data.startswith("SET_ZONE:"):
            zone_key = data.replace("SET_ZONE:", "").strip()
            await handle_set_zone(chat_id=user_chat_id, callback_query_id=cb_id, zone_key=zone_key)
            return

        # 3. Manejo de VIEW_FAV_{id} y LOAD_FAV_{id} (Renderizado Inmortal)
        if data.startswith("VIEW_FAV_") or data.startswith("LOAD_FAV_") or data.startswith("VIEW_FAV:"):
            clean_str = data.replace("VIEW_FAV_", "").replace("LOAD_FAV_", "").replace("VIEW_FAV:", "").strip()
            fav_id = int(clean_str) if clean_str.isdigit() else None
            await handle_view_favorite_card(chat_id=user_chat_id, fav_id=fav_id, callback_query_id=cb_id, user_id=caller_user_id)
            return

        # 4. Manejo de TOGGLE_CHART_{trend_id} (efecto toggle binario estricto entre gráfica y tendencia en grupo)
        if (data.startswith("TOGGLE_CHART") or data.startswith("TOGGLE_ORIGINAL")) and not data.startswith("TOGGLE_DM_ORIGINAL"):
            is_to_orig = ":original" in data or "_orig" in data or data.startswith("TOGGLE_ORIGINAL")
            import re
            m = re.search(r"\d+", data)
            t_id = int(m.group(0)) if m else trend_id
            await handle_toggle_chart(
                chat_id=user_chat_id,
                message_id=orig_msg_id,
                callback_query_id=cb_id,
                trend_id=t_id,
                to_original=is_to_orig
            )
            return

        # Regla estricta: en grupos está prohibido mostrar/procesar favoritos o profundizar
        if chat_type in ("group", "supergroup") and (
            action in ("SAVE_TREND", "save_favorite", "VIEW_FAVS", "view_favorites", "DEEP_DIVE", "deep_dive")
            or data.startswith("SAVE_TREND")
            or data.startswith("REMOVE_FAV")
            or data.startswith("VIEW_FAVS")
        ):
            await answer_callback_query(cb_id, text="⚠️ Esta función solo está disponible en chat privado con el bot.", show_alert=True)
            return

        # Manejo de REMOVE_FAV_{trend_id} o REMOVE_FAV:{trend_id}
        if data.startswith("REMOVE_FAV"):
            clean_tid = data.replace("REMOVE_FAV_", "").replace("REMOVE_FAV:", "").strip()
            rem_id = int(clean_tid) if clean_tid.isdigit() else None
            if rem_id is not None:
                await handle_remove_favorite(
                    chat_id=user_chat_id,
                    trend_id=rem_id,
                    callback_query_id=cb_id,
                    message_id=orig_msg_id,
                    user_id=caller_user_id
                )
            else:
                await answer_callback_query(cb_id, text="ID de tendencia no válido.", show_alert=True)
            return

        # Manejo de NOOP (botón ya presionado / guardado)
        if data == "NOOP":
            await answer_callback_query(cb_id, text="Esta tecnología ya está guardada en tus favoritos.")
            return

        # Manejo de MANAGE_FAVS (Ver o Gestionar Favoritos)
        if data == "MANAGE_FAVS":
            orig_text = str(msg_obj.get("text") or msg_obj.get("caption") or "")
            if "Tus tendencias guardadas" in orig_text:
                await handle_manage_favorites(
                    chat_id=user_chat_id,
                    message_id=orig_msg_id,
                    callback_query_id=cb_id,
                    user_id=caller_user_id
                )
            else:
                await handle_view_favorites(
                    chat_id=user_chat_id,
                    callback_query_id=cb_id,
                    user_id=caller_user_id
                )
            return

        if action in ("SAVE_TREND", "save_favorite") or data.startswith("SAVE_TREND"):
            clean_tid = data.replace("SAVE_TREND_", "").replace("SAVE_TREND:", "").replace("save_favorite:", "").strip()
            save_id = int(clean_tid) if clean_tid.isdigit() else trend_id
            await handle_save_trend(
                chat_id=user_chat_id,
                callback_query_id=cb_id,
                trend_id=save_id,
                message_id=orig_msg_id,
                current_reply_markup=msg_obj.get("reply_markup"),
                user_id=caller_user_id
            )
        elif action in ("VIEW_FAVS", "view_favorites") or data == "VIEW_FAVS":
            await handle_view_favorites(
                chat_id=user_chat_id,
                callback_query_id=cb_id,
                message_id=orig_msg_id,
                user_id=caller_user_id
            )
        elif action in ("VIEW_FAV", "LOAD_FAV", "GOTO_FAV", "goto_fav"):
            await handle_view_favorite_card(
                chat_id=user_chat_id,
                fav_id=trend_id,
                callback_query_id=cb_id,
                user_id=caller_user_id
            )
        elif action in ("GET_CHART", "view_chart") or data.startswith("GET_CHART"):
            clean_tid = data.replace("GET_CHART_", "").replace("GET_CHART:", "").replace("view_chart:", "").strip()
            chart_id = int(clean_tid) if clean_tid.isdigit() else trend_id
            await handle_get_chart(
                chat_id=user_chat_id,
                callback_query_id=cb_id,
                trend_id=chart_id,
                message_id=orig_msg_id,
                current_reply_markup=msg_obj.get("reply_markup"),
                to_original=False
            )
        elif action in ("TOGGLE_DM_ORIGINAL", "toggle_dm_original") or data.startswith("TOGGLE_DM_ORIGINAL"):
            clean_tid = data.replace("TOGGLE_DM_ORIGINAL_", "").replace("TOGGLE_DM_ORIGINAL:", "").strip()
            chart_id = int(clean_tid) if clean_tid.isdigit() else trend_id
            await handle_get_chart(
                chat_id=user_chat_id,
                callback_query_id=cb_id,
                trend_id=chart_id,
                message_id=orig_msg_id,
                current_reply_markup=msg_obj.get("reply_markup"),
                to_original=True
            )
        elif action in ("GET_STACK", "get_stack") or data.startswith("GET_STACK"):
            clean_tid = data.replace("GET_STACK_", "").replace("GET_STACK:", "").replace("get_stack:", "").strip()
            stack_id = int(clean_tid) if clean_tid.isdigit() else trend_id
            payload = {"action": "GET_STACK", "trend_id": stack_id}
            await open_private_chat(caller_user_id, payload, callback_query_id=cb_id)
        elif action in ("DEEP_DIVE", "deep_dive") or data.startswith("DEEP_DIVE"):
            clean_tid = data.replace("DEEP_DIVE_", "").replace("DEEP_DIVE:", "").replace("deep_dive:", "").strip()
            dd_id = int(clean_tid) if clean_tid.isdigit() else trend_id
            await handle_deep_dive(chat_id=user_chat_id, callback_query_id=cb_id, trend_id=dd_id)
        elif action == "RUN_RADAR_NOW":
            await answer_callback_query(cb_id, text="⚡ Generando tus tendencias personalizadas ahora...")
            from app.database import set_user_schedule, get_user_zone, get_user_industry
            # Establecer sin horario recurrente pero perfil completado
            set_user_schedule(user_chat_id, schedule_time="00:00")
            curr_zone = get_user_zone(user_chat_id) or "Global"
            curr_ind = get_user_industry(user_chat_id) or "TI & Software B2B"
            conf_msg = (
                "✅ <b>¡Configuración completada! Modo: Solo bajo demanda.</b>\n\n"
                f"• 🌎 <b>Mercado objetivo:</b> {curr_zone}\n"
                f"• 💼 <b>Industria / Nicho:</b> {curr_ind}\n\n"
                "<i>Generando y enviando tus tendencias ahora mismo...</i>"
            )
            await send_telegram_message(text=conf_msg, chat_id=user_chat_id)
            from app.main import run_individual_pipeline
            asyncio.create_task(run_individual_pipeline(chat_id=user_chat_id, ignore_daily_limit=True))

        elif action == "SET_SCHEDULE_NONE":
            await answer_callback_query(cb_id, text="🔕 Modo bajo demanda activado.")
            from app.database import set_user_schedule, get_user_zone, get_user_industry
            set_user_schedule(user_chat_id, schedule_time="00:00")
            curr_zone = get_user_zone(user_chat_id) or "Global"
            curr_ind = get_user_industry(user_chat_id) or "TI & Software B2B"
            conf_msg = (
                "✅ <b>¡Configuración completada! Modo: Solo bajo demanda.</b>\n\n"
                f"• 🌎 <b>Mercado objetivo:</b> {curr_zone}\n"
                f"• 💼 <b>Industria / Nicho:</b> {curr_ind}\n"
                "• ⏰ <b>Entrega diaria:</b> Desactivada (recibirás tendencias solo cuando presiones el botón)\n\n"
                "<i>Puedes consultar tus tendencias en cualquier momento usando el botón de abajo:</i>"
            )
            menu_kb = {
                "inline_keyboard": [
                    [{"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR"}],
                    [
                        {"text": "📁 Mis favoritos", "callback_data": "VIEW_FAVS"},
                        {"text": "⚙️ Configuración", "callback_data": "RESET_CONFIG"}
                    ]
                ]
            }
            await send_telegram_message(text=conf_msg, chat_id=user_chat_id, reply_markup=menu_kb)

        elif action in ("RUN_RADAR", "run_radar"):
            await answer_callback_query(cb_id, text="🚀 Ejecutando radar...")
            if chat_type in ("group", "supergroup"):
                from app.main import run_group_pipeline
                asyncio.create_task(run_group_pipeline(chat_id=user_chat_id))
            else:
                from app.main import run_individual_pipeline
                asyncio.create_task(run_individual_pipeline(chat_id=user_chat_id, ignore_daily_limit=True))
        else:
            await answer_callback_query(cb_id, text="Acción recibida.")
        return

    # 2. Manejo de Mensajes de Texto (Comandos y Onboarding Secuencial)
    if "message" in update:
        msg = update["message"]
        text = str(msg.get("text", "")).strip()
        user_chat_id = str(msg.get("chat", {}).get("id"))
        chat_type = msg.get("chat", {}).get("type", "private")

        if not text:
            return

        logger.info(f"[Telegram Bot] Mensaje recibido: '{text}' de chat_id={user_chat_id} (tipo={chat_type})")

        # 1. Deep links directos desde botones de grupo hacia la Rama B
        if text.startswith("/start stack_") or "stack_" in text:
            import re
            m = re.search(r"stack_(\d+)", text)
            target_id = int(m.group(1)) if m else None
            logger.info(f"[Telegram Bot] Deep-link detectado para Stack con trend_id={target_id} para chat {user_chat_id}")
            from app.rama_b import process_private_action
            await process_private_action(user_chat_id, {"action": "GET_STACK", "trend_id": target_id})
            return

        if text.startswith("/start scope_") or "scope_" in text:
            import re
            m = re.search(r"scope_(\d+)_?(\d*)", text)
            info_idx = int(m.group(1)) if m and m.group(1) else 0
            ret_idx = int(m.group(2)) if m and m.group(2) else 0
            logger.info(f"[Telegram Bot] Deep-link detectado para Scope con idx={info_idx} para chat {user_chat_id}")
            from app.rama_b import process_private_action
            await process_private_action(user_chat_id, {"action": "DEMANDA_SCOPE", "idx": info_idx, "return_idx": ret_idx})
            return

        if text.startswith("/start quote_") or "quote_" in text:
            import re
            m = re.search(r"quote_(\d+)_?(\d*)", text)
            info_idx = int(m.group(1)) if m and m.group(1) else 0
            ret_idx = int(m.group(2)) if m and m.group(2) else 0
            logger.info(f"[Telegram Bot] Deep-link detectado para Quote con idx={info_idx} para chat {user_chat_id}")
            from app.rama_b import process_private_action
            await process_private_action(user_chat_id, {"action": "DEMANDA_QUOTE", "idx": info_idx, "return_idx": ret_idx})
            return

        # 2. Deep link de Deep Dive desde el botón '🔍 Profundizar' del grupo público
        if "deepdive_" in text or text.startswith("/start deepdive"):
            import re
            m = re.search(r"deepdive_(\d+)", text)
            target_id = int(m.group(1)) if m else None
            logger.info(f"[Telegram Bot] Deep-link detectado para Deep Dive con trend_id={target_id} para chat {user_chat_id}")
            await send_telegram_message(
                text="🔍 <b>Analizando tecnología con Gemma...</b>\n\n<i>Generando tu auditoría y reporte técnico/comercial en privado...</i>",
                chat_id=user_chat_id
            )
            await handle_deep_dive(chat_id=user_chat_id, trend_id=target_id)
            return

        # 2. Reinicio o inicio de configuración (botón de grupo o comando /config / /reset)
        if text.startswith("/start config") or text == "/start config" or text in ("/config", "/reset"):
            if chat_type in ("group", "supergroup"):
                username = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
                await send_telegram_message(
                    text=f"⚙️ Para personalizar tu región e industria, inicia un chat privado con el bot: https://t.me/{username}?start=config",
                    chat_id=user_chat_id
                )
            else:
                from app.database import reset_user_config
                reset_user_config(user_chat_id)
                await send_telegram_message(text=WELCOME_INTRO_MSG, chat_id=user_chat_id)
                await send_telegram_message(text=STEP1_ZONE_MSG, chat_id=user_chat_id)
            return

        # 3. Onboarding Secuencial y Validación NLP en chat privado (DM)
        if chat_type == "private" and not text.startswith("/"):
            # Feedback visual instantáneo para el usuario
            asyncio.create_task(send_chat_action(action="typing", chat_id=user_chat_id))

            from app.database import (
                get_user_zone, get_user_industry, set_user_zone, set_user_industry,
                set_user_schedule, get_user_schedule,
                get_user_onboarding_step, reset_user_config
            )
            from app.llm_service import validate_zone, classify_user_input, parse_schedule_time

            fsm_step = get_user_onboarding_step(user_chat_id)
            logger.info(f"[Telegram Bot FSM] Usuario {user_chat_id} en estado '{fsm_step}'. Mensaje recibido: '{text}'")



            # ESTADO 3: ESPERANDO HORARIO (Paso 3 y Final)
            if fsm_step == "STEP_SCHEDULE":
                logger.info(f"[Telegram Bot] Procesando horario en Paso 3 para chat {user_chat_id}: '{text}'")
                sched_res = await parse_schedule_time(text)

                if not sched_res.get("valido"):
                    razon = sched_res.get("razon_rechazo") or "Por favor especifica una hora del día válida."
                    msg_reject = (
                        f"⚠️ {razon}\n\n"
                        "⏰ ¿A qué hora te gustaría recibir tu entrega diaria? (Ej. 08:30 AM, 2 de la tarde, 14:00)."
                    )
                    await send_telegram_message(text=msg_reject, chat_id=user_chat_id)
                    return

                norm_hora = sched_res.get("hora") or "10:00"
                set_user_schedule(user_chat_id, schedule_time=norm_hora)

                curr_zone = get_user_zone(user_chat_id) or "Global"
                curr_ind = get_user_industry(user_chat_id) or "TI & Software B2B"

                conf_msg = (
                    "✅ <b>¡Configuración completada! Tu radar está 100% activo.</b>\n\n"
                    f"• 🌎 <b>Mercado objetivo:</b> {curr_zone}\n"
                    f"• 💼 <b>Industria / Nicho:</b> {curr_ind}\n"
                    f"• ⏰ <b>Horario de entrega:</b> {norm_hora} hrs (diario)\n\n"
                    "<i>No tienes que esperar a tu hora programada para empezar a explorar hoy:</i>"
                )
                menu_kb = {
                    "inline_keyboard": [
                        [{"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR"}],
                        [
                            {"text": "📁 Mis favoritos", "callback_data": "VIEW_FAVS"},
                            {"text": "⚙️ Configuración", "callback_data": "RESET_CONFIG"}
                        ]
                    ]
                }
                await send_telegram_message(
                    text=conf_msg,
                    chat_id=user_chat_id,
                    reply_markup=menu_kb
                )
                return

            # ESTADO 2: ESPERANDO INDUSTRIA (Paso 2)
            if fsm_step == "STEP_INDUSTRY":
                logger.info(f"[Telegram Bot] Procesando EXCLUSIVAMENTE industria en Paso 2 para chat {user_chat_id}: '{text}'")
                class_res = await classify_user_input(text)

                curr_zone = get_user_zone(user_chat_id) or "tu región seleccionada"

                if not class_res.get("valido", False):
                    razon = class_res.get("razon_rechazo") or "El texto ingresado no es una industria o sector comercial válido."
                    # ⏳ = fallo técnico del LLM (no es culpa del usuario); ⚠️ = la entrada no es una industria válida
                    icono = "⏳" if class_res.get("error_tecnico") else "⚠️"
                    msg_reject = (
                        f"{icono} {razon}\n\n"
                        f"💼 ¿De qué industria te interesa conocer las tendencias en {curr_zone}? (Ej. Fintech, Salud, E-Commerce, Inteligencia Artificial, Logística)."
                    )
                    await send_telegram_message(text=msg_reject, chat_id=user_chat_id)
                    return

                detected_industry = class_res.get("industria_exacta") or class_res.get("industria") or "TI & Software B2B"
                categoria_api = class_res.get("categoria_api") or "general"
                set_user_industry(
                    user_chat_id,
                    industry=detected_industry,
                    industria_exacta=detected_industry,
                    categoria_api=categoria_api
                )

                # Transición natural al Paso 3: Horario diario o entrega inmediata
                msg_step3 = (
                    f"💼 Registramos la industria: <b>{detected_industry}</b>.\n\n"
                    "⏰ <b>Paso 3 de 3:</b> ¿En qué horario deseas recibir tus tendencias?\n\n"
                    "Puedes escribir una hora <i>(Ej. 08:30 AM, 14:00, 9 am)</i> para recibirlas a diario, "
                    "o presionar una de las opciones de abajo si solo deseas consultarlas bajo demanda:"
                )
                step3_kb = {
                    "inline_keyboard": [
                        [{"text": "⚡ Recibir tendencia ahora", "callback_data": "RUN_RADAR_NOW"}],
                        [{"text": "🔕 Solo bajo demanda (sin entrega diaria)", "callback_data": "SET_SCHEDULE_NONE"}]
                    ]
                }
                await send_telegram_message(text=msg_step3, chat_id=user_chat_id, reply_markup=step3_kb)
                return

            # ESTADO 1: ESPERANDO ZONA GEOGRÁFICA (Paso 1)
            if fsm_step == "STEP_ZONE":
                logger.info(f"[Telegram Bot] Validando zona en Paso 1: '{text}' para chat {user_chat_id}")
                val_res = await validate_zone(text)
                if not val_res.get("valido"):
                    razon = val_res.get("razon_rechazo") or "La región especificada no es válida o reconocible."
                    msg_reject = (
                        f"⚠️ {razon}\n\n"
                        f"{STEP1_ZONE_MSG}"
                    )
                    await send_telegram_message(text=msg_reject, chat_id=user_chat_id)
                    return

                zona_norm = val_res.get("zona_normalizada") or text.strip().title()
                z_local = val_res.get("zona_local")
                z_pais = val_res.get("zona_pais") or ""
                zonas_list = val_res.get("zonas") or []
                set_user_zone(user_chat_id, zone=zona_norm, zona_local=z_local, zona_pais=z_pais, zonas=zonas_list)

                # Si es localidad menor escalada, enviar mensaje explicativo primero
                if val_res.get("es_localidad_menor") and val_res.get("mensaje_escalado"):
                    await send_telegram_message(text=val_res["mensaje_escalado"], chat_id=user_chat_id)

                # Lógica de Renderizado Limpio (Capa UI):
                # - Si zona_local es null o vacía, imprime solo zona_pais (ej. "en Tailandia?")
                # - Si ambas existen, imprímelas juntas (ej. "en Monterrey, México?")
                if z_local and str(z_local).strip() and str(z_local).strip().lower() not in ("none", "null"):
                    if z_pais and str(z_pais).strip() and str(z_pais).strip().lower() != str(z_local).strip().lower() and str(z_pais).strip().lower() not in str(z_local).strip().lower():
                        display_zone = f"{str(z_local).strip()}, {str(z_pais).strip()}"
                    else:
                        display_zone = str(z_local).strip()
                else:
                    display_zone = str(z_pais).strip() if (z_pais and str(z_pais).strip().lower() not in ("none", "null")) else text.strip().title()

                # Paso 2: Preguntar por la industria en la zona seleccionada
                msg_step2 = f"💼 Perfecto. ¿De qué industria quieres conocer las tendencias en {display_zone}?"
                await send_telegram_message(text=msg_step2, chat_id=user_chat_id)
                return

            # ESTADO: COMPLETED (Perfil activo ya configurado previamente)
            curr_zone = get_user_zone(user_chat_id) or "Global"
            curr_ind = get_user_industry(user_chat_id) or "TI & Software B2B"
            ready_msg = (
                f"💡 Tu perfil activo está configurado para <b>{curr_zone}</b> e industria <b>{curr_ind}</b>.\n\n"
                "• Usa <code>/radar</code> para consultar una nueva tendencia de hoy.\n"
                "• Presiona <b>⚙️ Reconfigurar radar</b> si deseas cambiar tu región o industria."
            )
            reconfig_kb = {
                "inline_keyboard": [
                    [{"text": "⚙️ Reconfigurar radar", "callback_data": "RESET_CONFIG"}],
                    [{"text": "🚀 Consultar radar ahora", "callback_data": "RUN_RADAR"}]
                ]
            }
            await send_telegram_message(text=ready_msg, chat_id=user_chat_id, reply_markup=reconfig_kb)
            return

        # Si el usuario ejecuta /start puro en DM y no tiene configuración completa (o primera vez)
        if text == "/start" and chat_type == "private":
            from app.database import get_user_onboarding_step, reset_user_config
            fsm_step = get_user_onboarding_step(user_chat_id)
            if fsm_step != "COMPLETED":
                reset_user_config(user_chat_id)
                await send_telegram_message(text=WELCOME_INTRO_MSG, chat_id=user_chat_id)
                await send_telegram_message(text=STEP1_ZONE_MSG, chat_id=user_chat_id)
                return

        if text.startswith("/zona"):
            if chat_type in ("group", "supergroup"):
                username = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
                await send_telegram_message(
                    text=f"⚙️ Para configurar tu zona personalizada de alertas, inicia un chat privado con el bot: https://t.me/{username}?start=config",
                    chat_id=user_chat_id
                )
            else:
                await handle_zone_command(chat_id=user_chat_id)
        elif text.startswith("/favoritos"):
            if chat_type in ("group", "supergroup"):
                username = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
                await send_telegram_message(
                    text=f"📁 Tus favoritos son privados. Consúltalos en tu chat directo con el bot: https://t.me/{username}?start=config",
                    chat_id=user_chat_id
                )
            else:
                msg_from_user = msg.get("from", {})
                caller_user_id = msg_from_user.get("id") or (int(user_chat_id) if user_chat_id.isdigit() else user_chat_id)
                await handle_view_favorites(chat_id=user_chat_id, user_id=caller_user_id)
        elif text.startswith("/grafica") or text.startswith("/chart"):
            await handle_get_chart(chat_id=user_chat_id)
        elif text.startswith("/profundizar") or text.startswith("/deepdive"):
            if chat_type in ("group", "supergroup"):
                username = (settings.TELEGRAM_BOT_USERNAME or "Tendencias_DiegoBot").lstrip("@")
                await send_telegram_message(
                    text=f"🔍 Para reportes profundos de herramientas, consúltalos en privado: https://t.me/{username}?start=config",
                    chat_id=user_chat_id
                )
            else:
                await handle_deep_dive(chat_id=user_chat_id)
        elif text.startswith("/start") or text.startswith("/help") or text.startswith("/ayuda"):
            welcome = (
                "👋 <b>Bienvenido al Agente de Inteligencia Comercial B2B</b>\n\n"
                "Monitoreo diario automatizado de tendencias tecnológicas de alto impacto comercial.\n\n"
                "<b>Comandos disponibles:</b>\n"
                "• <code>/radar</code> o <code>/hoy</code> : Generar y enviar el radar de hoy inmediatamente.\n"
                "• <code>/industria</code> : Configurar la industria o sector de interés (Fintech, Ciberseguridad, Salud, etc.).\n"
                "• <code>/zona</code> : Configurar la región geográfica preferida (Global, México, EE.UU., Europa, Colombia).\n"
                "• <code>/favoritos</code> : Listar todas tus tecnologías guardadas con citas a sus tarjetas originales.\n"
                "• <code>/grafica</code> : Visualizar la gráfica de tracción semanal.\n"
                "• <code>/profundizar</code> : Generar reporte denso sobre la última tecnología.\n\n"
                "<i>También puedes interactuar directamente usando los botones debajo de cada tarjeta.</i>"
            )
            await send_telegram_message(text=welcome, chat_id=user_chat_id)
        elif text.startswith("/radar") or text.startswith("/hoy"):
            if chat_type in ("group", "supergroup"):
                await send_telegram_message(
                    text="🚀 <i>Ejecutando radar para el grupo (Alcance Global)... Te enviaré la tarjeta en un momento.</i>",
                    chat_id=user_chat_id
                )
                from app.main import run_group_pipeline
                asyncio.create_task(run_group_pipeline(chat_id=user_chat_id))
            else:
                await send_telegram_message(
                    text="🚀 <i>Ejecutando tu radar diario personalizado... Te enviaré la tarjeta en un momento.</i>",
                    chat_id=user_chat_id
                )
                from app.main import run_individual_pipeline
                asyncio.create_task(run_individual_pipeline(chat_id=user_chat_id))


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
    client = get_http_client()
    try:
        await client.post(f"https://api.telegram.org/bot{bot_token}/deleteWebhook")
    except Exception:
        pass

    offset = 0
    logger.info("[Telegram Bot] Long Polling iniciado exitosamente. Escuchando eventos...")

    while _polling_active:
        try:
            url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
            params = {"offset": offset, "timeout": 15}
            resp = await client.get(url, params=params, timeout=25.0)

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
    """Detiene limpiamente el listener de Long Polling y cierra la conexion HTTP persistente."""
    global _polling_active, _polling_task
    _polling_active = False
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
        _polling_task = None
    await close_http_client()
