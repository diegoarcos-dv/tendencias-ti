"""Capa de Orquestación: Servidor Principal FastAPI y Cron APScheduler.

Pipeline Diario:
1. Ingesta (Product Hunt, Reddit, Google Trends)
2. Scoring Engine (Filtra la tendencia Top 1)
3. IA Local (Ollama / Gemma)
4. Motor Visual (Playwright HTML -> PNG 1080x1080px)
5. Notificación Telegram (API oficial con Markdown e Inline Keyboards)
"""

from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio
import logging
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.context_reader import business_context
from app.connectors import (
    TrendItem,
    ProductHuntConnector,
    RedditB2BConnector,
    GoogleTrendsConnector,
    fetch_all_trends,
)
from app.database import (
    init_db,
    save_trend,
    trend_exists,
    get_trend_by_id,
    get_favorites,
    get_recent_sent_trends,
    get_user_zone,
    get_user_daily_card_count,
    get_expired_card_messages,
    delete_card_record,
)
from app.llm_service import generate_trend_card_data
from app.visual_engine import create_png_card
from app.telegram_bot import (
    send_telegram_notification,
    build_interactive_keyboard,
    build_group_keyboard,
    delete_telegram_message,
    start_bot_polling,
    stop_bot_polling,
    process_telegram_update,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app.main")

# Instancia global del Scheduler asíncrono
scheduler = AsyncIOScheduler()


# ============================================================================
# Scoring Engine
# ============================================================================

def select_top_trend(trends: List[TrendItem], days_cooldown: Optional[int] = None) -> Optional[TrendItem]:
    """Scoring Engine: Selecciona la herramienta o solución técnica 'Top 1' del día.

    Aplica:
    1. Filtro estricto anti-duplicados (descarta tendencias ya enviadas en la ventana de cooldown).
    2. Afinidad temática estricta con la fuente de verdad del negocio.
    3. Especificidad funcional (prioriza herramientas y productos de software concretos).
    4. Nivel de tracción cuantitativa (upvotes, interacciones y volumen de interés).
    """
    if not trends:
        return None

    # Asegurar base de datos inicializada
    init_db()

    cooldown = days_cooldown if days_cooldown is not None else settings.DEDUPLICATION_WINDOW_DAYS

    # 1. Filtro Anti-Duplicados
    fresh_trends: List[TrendItem] = []
    skipped_count = 0
    for item in trends:
        if trend_exists(url=item.url, title=item.title, days_cooldown=cooldown):
            skipped_count += 1
        else:
            fresh_trends.append(item)

    logger.info(
        f"[Scoring Engine] Total recibidas: {len(trends)} | "
        f"Descartadas por historial reciente ({cooldown} días): {skipped_count} | "
        f"Frescas disponibles: {len(fresh_trends)}"
    )

    if not fresh_trends:
        logger.warning(
            f"[Scoring Engine] Todas las tendencias candidatas ({len(trends)}) ya fueron enviadas en los últimos {cooldown} días."
        )
        return None

    def calculate_tool_score(item: TrendItem) -> float:
        # Relevancia con el archivo de negocio
        affinity_score = 5000.0 if item.business_relevant else 0.0
        
        # Ponderación decisiva por especificidad de producto/herramienta de software concreta
        tool_bonus = 0.0
        if item.source == "product_hunt":
            tool_bonus = 2500.0  # Productos de software lanzados al mercado con servicios específicos
        elif item.source == "reddit":
            tool_bonus = 1500.0  # Soluciones y discusiones técnicas B2B de desarrolladores

        # Tracción cuantitativa real
        normalized_traction = min(item.metric_score, 1000.0)

        return affinity_score + tool_bonus + normalized_traction

    sorted_trends = sorted(fresh_trends, key=calculate_tool_score, reverse=True)
    top_1 = sorted_trends[0]
    logger.info(
        f"Top 1 seleccionado por el Scoring Engine: '{top_1.title}' "
        f"[Fuente: {top_1.source}, Métrica: {top_1.metric_score}, Relevante: {top_1.business_relevant}]"
    )
    return top_1


# ============================================================================
# Pipelines: Grupo Público vs. Chat Privado (DM) y Caducidad TTL
# ============================================================================

async def run_group_pipeline(chat_id: Optional[str] = None) -> Dict[str, Any]:
    """1. Pipeline de Grupo: Alcance 100% Global, teclado con un ÚNICO botón deep link.
    Horarios estrictos: 10:00, 14:00 y 18:00.
    """
    target_chat = chat_id or settings.TELEGRAM_GROUP_CHAT_ID
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"INICIANDO PIPELINE DE GRUPO (GLOBAL) [{start_time}] -> Chat: {target_chat}")
    logger.info("=" * 60)

    # 1. Ingesta con alcance Global
    all_trends = fetch_all_trends(zone="Global")
    top_trend = select_top_trend(all_trends)
    if not top_trend:
        logger.error("[Pipeline Grupo] No hay tendencias frescas disponibles.")
        return {"status": "error", "message": "No fresh trends available"}

    # 2. Análisis con Gemma enfocado en Global
    trend_dict = {**top_trend.model_dump(), "geo_region": "Global"}
    card_data = await generate_trend_card_data(
        trend_data=trend_dict,
        business_context_text=business_context.raw_content
    )

    # 3. Renderizado con Playwright
    target_png = settings.BASE_DIR / "temp_group_card.png"
    await create_png_card(data=card_data, output_path=target_png)

    # 4. Persistencia en SQLite
    trend_id = save_trend(trend_data=top_trend.model_dump(), card_data=card_data)

    # 5. Envío al grupo con botones deep-link hacia el DM ("🔍 Profundizar" y "🤖 Personalizar alertas")
    group_markup = build_group_keyboard(trend_id=trend_id)
    telegram_result = await send_telegram_notification(
        photo_path=target_png,
        caption="",
        reply_markup=group_markup,
        chat_id=target_chat,
        chat_type="group",
        trend_id=trend_id
    )

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"PIPELINE DE GRUPO COMPLETADO EN {duration:.2f}s")
    return {
        "status": "success",
        "chat_type": "group",
        "chat_id": target_chat,
        "trend_id": trend_id,
        "duration_seconds": duration,
        "telegram_result": telegram_result
    }


async def run_individual_pipeline(chat_id: Optional[str] = None) -> Dict[str, Any]:
    """2. Pipeline Individual (DM): Segmentado por la zona del usuario, menú completo de 4 botones.
    Respeta el límite estricto de 3 envíos diarios por usuario.
    """
    target_chat = chat_id or settings.TELEGRAM_CHAT_ID
    start_time = datetime.now()

    # Verificar límite estricto de 3 envíos diarios por usuario
    daily_count = get_user_daily_card_count(str(target_chat))
    max_daily = settings.USER_DAILY_SEND_LIMIT
    if daily_count >= max_daily:
        msg = f"Límite diario alcanzado ({daily_count}/{max_daily}) para el chat {target_chat}."
        logger.warning(f"[Pipeline Individual] {msg}")
        return {
            "status": "skipped",
            "reason": "daily_limit_reached",
            "daily_count": daily_count,
            "max_daily": max_daily,
            "message": msg
        }

    logger.info("=" * 60)
    logger.info(f"INICIANDO PIPELINE INDIVIDUAL [{start_time}] -> Chat: {target_chat} (Envío {daily_count + 1}/{max_daily})")
    logger.info("=" * 60)

    # 1. Obtener zona preferida del usuario
    user_zone = get_user_zone(str(target_chat))
    all_trends = fetch_all_trends(zone=user_zone)
    top_trend = select_top_trend(all_trends)
    if not top_trend:
        logger.error("[Pipeline Individual] No hay tendencias frescas disponibles.")
        return {"status": "error", "message": "No fresh trends available"}

    # 2. Análisis con Gemma enfocado en la zona del usuario
    trend_dict = {**top_trend.model_dump(), "geo_region": user_zone}
    card_data = await generate_trend_card_data(
        trend_data=trend_dict,
        business_context_text=business_context.raw_content
    )

    # 3. Renderizado con Playwright
    target_png = settings.BASE_DIR / "temp_card.png"
    await create_png_card(data=card_data, output_path=target_png)

    # 4. Persistencia en SQLite
    trend_id = save_trend(trend_data=top_trend.model_dump(), card_data=card_data)

    # 5. Envío a Telegram con el panel interactivo completo (4 botones)
    reply_markup = build_interactive_keyboard(trend_id=trend_id, source_url=top_trend.url)
    telegram_result = await send_telegram_notification(
        photo_path=target_png,
        caption="",
        reply_markup=reply_markup,
        chat_id=target_chat,
        chat_type="private"
    )

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"PIPELINE INDIVIDUAL COMPLETADO EN {duration:.2f}s")
    return {
        "status": "success",
        "chat_type": "private",
        "chat_id": target_chat,
        "zone": user_zone,
        "trend_id": trend_id,
        "duration_seconds": duration,
        "telegram_result": telegram_result
    }


async def cleanup_expired_messages(days: Optional[int] = None) -> Dict[str, Any]:
    """3. Caducidad de Mensajes (TTL de 7 días): Elimina en Telegram (deleteMessage)
    y en SQLite las tarjetas con más de 7 días de antigüedad.
    """
    ttl_days = days or settings.CARD_TTL_DAYS
    logger.info(f"[TTL Cleanup] Iniciando depuración de mensajes con más de {ttl_days} días de antigüedad...")
    expired = get_expired_card_messages(days=ttl_days)
    deleted_telegram = 0
    cleaned_records = 0

    for item in expired:
        rec_id = item["id"]
        c_id = item["chat_id"]
        m_id = item["message_id"]
        try:
            ok = await delete_telegram_message(chat_id=c_id, message_id=m_id)
            if ok:
                deleted_telegram += 1
            delete_card_record(rec_id)
            cleaned_records += 1
        except Exception as e:
            logger.error(f"[TTL Cleanup] Error depurando mensaje {m_id} en chat {c_id}: {e}")

    logger.info(f"[TTL Cleanup] Proceso completado. Eliminados en Telegram: {deleted_telegram} | Registros purgados: {cleaned_records}")
    return {
        "status": "success",
        "ttl_days": ttl_days,
        "found_expired": len(expired),
        "deleted_telegram": deleted_telegram,
        "cleaned_records": cleaned_records
    }


# Alias de compatibilidad
run_daily_pipeline = run_individual_pipeline


# ============================================================================
# Ciclo de Vida de FastAPI y Configuración del Cron
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de FastAPI: inicializa DB, contexto, polling de Telegram y cronogramas independientes."""
    logger.info("Inicializando Agente de Inteligencia Comercial...")
    init_db()
    business_context.load_context()

    # Iniciar Long Polling de Telegram en segundo plano para escuchar botones y comandos
    await start_bot_polling()

    # 1. Cronograma Estricto del Grupo Público: 10:00, 14:00 y 18:00
    scheduler.add_job(
        run_group_pipeline,
        trigger=CronTrigger(hour="10,14,18", minute=0),
        id="group_intelligence_pipeline_10_14_18",
        name="Pipeline Grupo TI (10:00, 14:00, 18:00)",
        replace_existing=True
    )
    logger.info("Cron de Grupo programado: estrictamente a las 10:00, 14:00 y 18:00.")

    # 2. Cronograma de Notificaciones Individuales (DMs): Respeta límite de 3 envíos/día
    # Programado por defecto en la hora configurada (07:00 AM) y franjas complementarias
    hour, minute = 7, 0
    try:
        parts = settings.SCHEDULE_TIME.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    except Exception as e:
        logger.warning(f"Error parseando SCHEDULE_TIME ({settings.SCHEDULE_TIME}): {e}. Usando 07:00.")

    scheduler.add_job(
        run_individual_pipeline,
        trigger=CronTrigger(hour=hour, minute=minute),
        id="individual_intelligence_pipeline_daily",
        name=f"Pipeline Individual Diario ({hour:02d}:{minute:02d})",
        replace_existing=True
    )
    logger.info(f"Cron Individual programado: diario a las {hour:02d}:{minute:02d} (máx 3 envíos/día).")

    # 3. Tarea Diaria de Caducidad de Mensajes (TTL 7 Días): Corre a las 03:00 AM
    scheduler.add_job(
        cleanup_expired_messages,
        trigger=CronTrigger(hour=3, minute=0),
        id="cleanup_expired_cards_daily",
        name="Depuración Diaria TTL Tarjetas 7 Días (03:00 AM)",
        replace_existing=True
    )
    logger.info("Cron de Caducidad (TTL 7 días) programado: diariamente a las 03:00 AM.")

    scheduler.start()

    yield

    logger.info("Deteniendo Long Polling de Telegram y APScheduler...")
    await stop_bot_polling()
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="Agente de Inteligencia Comercial",
    description="Backend orquestador para ingesta, filtrado con fuente de verdad y entrega visual de tendencias a Telegram.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Endpoints de API
# ============================================================================

@app.get("/health", tags=["Salud"])
async def health_check() -> Dict[str, Any]:
    """Endpoint de estado del servidor, scheduler y memoria."""
    jobs = [
        {"id": j.id, "name": j.name, "next_run_time": str(j.next_run_time)}
        for j in scheduler.get_jobs()
    ]
    return {
        "status": "healthy",
        "app_env": settings.APP_ENV,
        "context_loaded": bool(business_context.raw_content),
        "scheduler_running": scheduler.running,
        "scheduled_jobs": jobs,
        "ollama_model": settings.OLLAMA_MODEL,
        "telegram_configured": bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID),
    }


@app.get("/api/v1/context", tags=["Contexto de Negocio"])
async def get_business_context() -> Dict[str, Any]:
    """Devuelve la fuente de verdad del negocio residente en memoria."""
    return {
        "file_path": str(settings.BUSINESS_CONTEXT_FILE),
        "total_characters": len(business_context.raw_content),
        "categories": business_context.categories,
        "keywords_sample": list(business_context.keywords)[:20],
    }


@app.post("/api/v1/pipeline/trigger", tags=["Orquestación"])
async def trigger_pipeline_now() -> Dict[str, Any]:
    """Fuerza la ejecución inmediata del pipeline individual completo."""
    result = await run_individual_pipeline()
    return result


@app.post("/api/v1/pipeline/group", tags=["Orquestación"])
async def trigger_group_pipeline_endpoint(chat_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Fuerza la ejecución del pipeline para el grupo de Telegram (Alcance Global, 1 botón deep link)."""
    return await run_group_pipeline(chat_id=chat_id)


@app.post("/api/v1/pipeline/individual", tags=["Orquestación"])
async def trigger_individual_pipeline_endpoint(chat_id: Optional[str] = Query(default=None)) -> Dict[str, Any]:
    """Fuerza la ejecución del pipeline individual (Enfoque por zona, menú 4 botones, límite 3 envíos/día)."""
    return await run_individual_pipeline(chat_id=chat_id)


@app.post("/api/v1/pipeline/cleanup-expired", tags=["Orquestación"])
async def trigger_cleanup_expired_endpoint(days: int = Query(default=7, ge=1, le=90)) -> Dict[str, Any]:
    """Fuerza la ejecución de la limpieza TTL (7 días) eliminando mensajes en Telegram y SQLite."""
    return await cleanup_expired_messages(days=days)


@app.get("/api/v1/sources/test", response_model=List[TrendItem], tags=["Ingesta"])
async def test_all_sources(limit: int = Query(default=15, ge=1, le=50)) -> List[TrendItem]:
    """Ejecuta los conectores de ingesta y retorna los datos unificados."""
    trends = fetch_all_trends()
    return trends[:limit]


@app.get("/api/v1/history", tags=["Historial"])
async def get_history(limit: int = Query(default=20, ge=1, le=100)) -> Dict[str, Any]:
    """Retorna el historial de tendencias enviadas ordenadas cronológicamente."""
    history = get_recent_sent_trends(limit=limit)
    return {"total": len(history), "trends": history}


@app.get("/api/v1/favorites", tags=["Favoritos"])
async def get_all_favorites() -> Dict[str, Any]:
    """Retorna las tendencias guardadas como favoritas."""
    favorites = get_favorites()
    return {"total": len(favorites), "favorites": favorites}


@app.get("/api/v1/trend/{trend_id}", tags=["Historial"])
async def get_single_trend(trend_id: int) -> Dict[str, Any]:
    """Obtiene el detalle completo de una tendencia por su ID."""
    trend = get_trend_by_id(trend_id)
    if not trend:
        raise HTTPException(status_code=404, detail="Tendencia no encontrada")
    return trend


@app.post("/api/v1/telegram/webhook", tags=["Telegram"])
async def telegram_webhook(update: Dict[str, Any], background_tasks: BackgroundTasks) -> Dict[str, Any]:
    """Endpoint de webhook alternativo para recibir eventos de Telegram en tiempo real."""
    background_tasks.add_task(process_telegram_update, update)
    return {"ok": True, "message": "Update recibido"}


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False
    )
