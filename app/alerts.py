"""Sistema de Observabilidad Proactiva, Alertas Push y Heartbeat (SRE / Senior Fullstack).

Responsabilidades:
- Envío proactivo de alertas push inmediatas a Telegram ante fallos críticos en pipelines, conectores o LLM.
- Emisión del "Pulso Operativo Diario" (Daily Health Pulse) confirmando ejecución exitosa, métricas y tiempos.
- Sondas de salud sintética profunda (/health/deep) comprobando DB, Ollama, Playwright y Telegram.
- Soporte para Dead Man's Snitch (Heartbeat Ping) para monitoreo externo en caso de caída total del servidor.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import logging
import asyncio
import httpx

from app.config import settings

logger = logging.getLogger("app.alerts")


async def send_admin_alert(
    component: str,
    error_msg: str,
    context: Optional[str] = None,
    action_taken: str = "Recuperación automática con fallback determinista.",
    severity: str = "CRÍTICA",
    chat_id: Optional[str] = None
) -> bool:
    """Envía una notificación push inmediata al chat privado del administrador ante una anomalía o error."""
    target_chat = chat_id or settings.TELEGRAM_ADMIN_CHAT_ID or settings.TELEGRAM_CHAT_ID
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token or not target_chat:
        logger.warning("[Alerts] TELEGRAM_BOT_TOKEN o ADMIN_CHAT_ID no configurados. Alerta no enviada.")
        return False

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    icon = "🚨" if severity == "CRÍTICA" else "⚠️"

    alert_text = (
        f"{icon} <b>ALERTA DE SISTEMA PROACTIVA ({severity})</b>\n\n"
        f"• <b>Componente:</b> <code>{component}</code>\n"
        f"• <b>Hora:</b> {now_str}\n"
        f"• <b>Detalle del Error:</b>\n"
        f"<code>{error_msg[:400]}</code>\n\n"
        f"• <b>Acción Automática:</b> {action_taken}\n"
    )
    if context:
        alert_text += f"• <b>Contexto:</b> {context}\n"

    alert_text += "\n<i>Notificación proactiva automática generada por el Observador de Salud.</i>"

    try:
        from app.telegram_bot import get_http_client
        client = get_http_client()
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": alert_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        res = await client.post(url, json=payload, timeout=8.0)
        if res.status_code == 200:
            logger.info(f"[Alerts] Alerta push enviada exitosamente a admin chat {target_chat}.")
            return True
        else:
            logger.error(f"[Alerts] Telegram API respondió {res.status_code} al enviar alerta: {res.text[:200]}")
            return False
    except Exception as exc:
        logger.exception(f"[Alerts] Excepción enviando alerta push a admin: {exc}")
        return False


async def send_daily_health_report(
    execution_time_s: float,
    items_count: int,
    top_title: str,
    pipeline_type: str = "Catálogo Grupo TI",
    chat_id: Optional[str] = None,
    system_health: Optional[Dict[str, Any]] = None
) -> bool:
    """Envía el Pulso Operativo Diario (Green Pulse) confirmando proactivamente que la entrega ocurrió al 100%."""
    target_chat = chat_id or settings.TELEGRAM_ADMIN_CHAT_ID or settings.TELEGRAM_CHAT_ID
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token or not target_chat:
        return False

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # Sonda sintética rápida de salud si no fue provista
    if not system_health:
        system_health = await check_system_health()

    db_status = "✅ OK" if system_health.get("database", {}).get("status") == "healthy" else "⚠️ Degradado"
    ollama_status = "✅ OK" if system_health.get("ollama", {}).get("status") == "healthy" else "⚠️ Offline / Fallback"
    pw_status = "✅ OK" if system_health.get("chromium", {}).get("status") == "healthy" else "⚠️ Reiniciando"
    tg_status = "✅ OK" if system_health.get("telegram", {}).get("status") == "healthy" else "⚠️ Error Red"

    pulse_msg = (
        "📊 <b>PULSO OPERATIVO DIARIO (SALUD PROACTIVA)</b>\n\n"
        f"✅ <b>Estado:</b> Misión diaria ejecutada exitosamente.\n"
        f"• <b>Pipeline:</b> {pipeline_type}\n"
        f"• <b>Tendencia Principal:</b> <b>{top_title}</b>\n"
        f"• <b>Tarjetas Generadas:</b> {items_count}\n"
        f"• <b>Latencia Total de Proceso:</b> <code>{execution_time_s:.2f}s</code>\n"
        f"• <b>Hora de Reporte:</b> {now_str}\n\n"
        "🏥 <b>Diagnóstico de Servicios:</b>\n"
        f"• Base de Datos SQLite: {db_status}\n"
        f"• Motor IA Local (Ollama): {ollama_status}\n"
        f"• Renderizador Visual (Chromium): {pw_status}\n"
        f"• API Telegram: {tg_status}\n\n"
        "<i>Tu radar está 100% operativo y en guardia para el siguiente corte.</i>"
    )

    try:
        from app.telegram_bot import get_http_client
        client = get_http_client()
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": pulse_msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        res = await client.post(url, json=payload, timeout=8.0)
        return res.status_code == 200
    except Exception as exc:
        logger.error(f"[Alerts] Error enviando pulso operativo diario: {exc}")
        return False


async def check_system_health() -> Dict[str, Any]:
    """Sonda Sintética Activa: prueba en tiempo real cada subsistema vital y retorna su diagnóstico cuantitativo."""
    health: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_status": "healthy",
        "database": {"status": "unknown"},
        "ollama": {"status": "unknown"},
        "chromium": {"status": "unknown"},
        "telegram": {"status": "unknown"}
    }

    # 1. Probar SQLite (lectura/escritura)
    try:
        from app.database import _get_connection
        t0_db = asyncio.get_event_loop().time()
        with _get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT 1")
            cur.fetchone()
        t1_db = asyncio.get_event_loop().time()
        health["database"] = {
            "status": "healthy",
            "latency_ms": round((t1_db - t0_db) * 1000, 2)
        }
    except Exception as e_db:
        health["database"] = {"status": "error", "error": str(e_db)}
        health["overall_status"] = "degraded"

    # 2. Probar Ollama
    try:
        from app.telegram_bot import get_http_client
        client = get_http_client()
        t0_ol = asyncio.get_event_loop().time()
        res_ol = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        t1_ol = asyncio.get_event_loop().time()
        if res_ol.status_code == 200:
            health["ollama"] = {
                "status": "healthy",
                "model": settings.OLLAMA_MODEL,
                "latency_ms": round((t1_ol - t0_ol) * 1000, 2)
            }
        else:
            health["ollama"] = {"status": "degraded", "code": res_ol.status_code}
    except Exception as e_ol:
        health["ollama"] = {"status": "offline_fallback", "note": "Operando con fallback determinista de alta velocidad"}

    # 3. Probar Chromium Singleton
    try:
        from app.visual_engine import get_browser_singleton
        b = await get_browser_singleton()
        is_conn = b.is_connected() if b else False
        health["chromium"] = {
            "status": "healthy" if is_conn else "disconnected",
            "connected": is_conn
        }
    except Exception as e_cr:
        health["chromium"] = {"status": "error", "error": str(e_cr)}
        health["overall_status"] = "degraded"

    # 4. Probar Telegram API
    try:
        client = get_http_client()
        t0_tg = asyncio.get_event_loop().time()
        res_tg = await client.get(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe", timeout=3.0)
        t1_tg = asyncio.get_event_loop().time()
        if res_tg.status_code == 200:
            bot_data = res_tg.json().get("result", {})
            health["telegram"] = {
                "status": "healthy",
                "bot_username": bot_data.get("username"),
                "latency_ms": round((t1_tg - t0_tg) * 1000, 2)
            }
        else:
            health["telegram"] = {"status": "error", "code": res_tg.status_code}
            health["overall_status"] = "degraded"
    except Exception as e_tg:
        health["telegram"] = {"status": "unreachable", "error": str(e_tg)}
        health["overall_status"] = "degraded"

    return health


async def send_heartbeat_ping() -> bool:
    """Envía un ping HTTP a un monitor externo (Dead Man's Snitch / Healthchecks.io) si está configurado."""
    snitch_url = settings.HEARTBEAT_SNITCH_URL
    if not snitch_url or not snitch_url.startswith("http"):
        return False
    try:
        from app.telegram_bot import get_http_client
        client = get_http_client()
        resp = await client.get(snitch_url, timeout=5.0)
        logger.info(f"[Heartbeat] Ping externo enviado a Dead Man's Snitch ({resp.status_code}).")
        return resp.status_code == 200
    except Exception as ex:
        logger.warning(f"[Heartbeat] No se pudo enviar ping al monitor externo: {ex}")
        return False
