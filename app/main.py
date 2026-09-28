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
)
from app.llm_service import generate_trend_card_data
from app.visual_engine import create_png_card
from app.telegram_bot import (
    send_telegram_notification,
    build_interactive_keyboard,
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
# Pipeline Diario Completo
# ============================================================================

async def run_daily_pipeline() -> Dict[str, Any]:
    """Ejecuta el pipeline completo de Inteligencia Comercial de extremo a extremo:

    Extracción -> Scoring -> Gemma -> Playwright -> Persistencia -> Telegram
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info(f"INICIANDO PIPELINE DIARIO DE INTELIGENCIA COMERCIAL [{start_time}]")
    logger.info("=" * 60)

    # 1. Extracción de fuentes
    logger.info("[Paso 1/6] Ingestando datos de Product Hunt, Reddit y Google Trends...")
    all_trends = fetch_all_trends()
    logger.info(f"Tendencias recolectadas: {len(all_trends)}")

    # 2. Scoring Engine con filtro anti-duplicados
    logger.info("[Paso 2/6] Evaluando tendencias con el Scoring Engine (Filtro Anti-Duplicados)...")
    top_trend = select_top_trend(all_trends)
    if not top_trend:
        logger.error("No se pudo seleccionar ninguna tendencia fresca. Pipeline abortado.")
        return {"status": "error", "message": "No fresh trends available"}

    # 3. Análisis con IA Local (Gemma)
    logger.info("[Paso 3/6] Consultando a Gemma para generar impacto comercial y stack...")
    context_text = business_context.raw_content
    card_data = await generate_trend_card_data(
        trend_data=top_trend.model_dump(),
        business_context_text=context_text
    )

    # 4. Renderizado con Playwright (1080x1080px)
    logger.info("[Paso 4/6] Renderizando tarjeta visual en PNG con Playwright...")
    target_png = settings.BASE_DIR / "temp_card.png"
    await create_png_card(data=card_data, output_path=target_png)

    # 5. Persistencia en Base de Datos SQLite (radar.db)
    logger.info("[Paso 5/6] Persistiendo tendencia en base de datos SQLite (radar.db)...")
    trend_id = save_trend(trend_data=top_trend.model_dump(), card_data=card_data)
    logger.info(f"Tendencia registrada en historial_envios con ID: {trend_id}")

    # 6. Envío a Telegram con los 4 botones interactivos solicitados
    logger.info("[Paso 6/6] Enviando temp_card.png al chat de Telegram con panel interactivo...")
    reply_markup = build_interactive_keyboard(trend_id=trend_id, source_url=top_trend.url)
    telegram_result = await send_telegram_notification(
        photo_path=target_png,
        caption="",
        reply_markup=reply_markup,
        parse_mode=None
    )

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"PIPELINE DIARIO COMPLETADO EN {duration:.2f} SEGUNDOS")

    return {
        "status": "success",
        "duration_seconds": duration,
        "trend_id": trend_id,
        "top_trend": top_trend.model_dump(),
        "card_data": card_data,
        "image_path": str(target_png),
        "telegram_result": telegram_result
    }


# ============================================================================
# Ciclo de Vida de FastAPI y Configuración del Cron
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de FastAPI: inicializa DB, contexto, polling de Telegram y programa cron diario."""
    logger.info("Inicializando Agente de Inteligencia Comercial...")
    init_db()
    business_context.load_context()

    # Iniciar Long Polling de Telegram en segundo plano para escuchar botones y comandos
    await start_bot_polling()

    # Parsear hora programada (default 07:00)
    hour, minute = 7, 0
    try:
        parts = settings.SCHEDULE_TIME.split(":")
        hour, minute = int(parts[0]), int(parts[1])
    except Exception as e:
        logger.warning(f"Error parseando SCHEDULE_TIME ({settings.SCHEDULE_TIME}): {e}. Usando 07:00.")

    # Programar cron diario a las 07:00 AM
    trigger = CronTrigger(hour=hour, minute=minute)
    scheduler.add_job(
        run_daily_pipeline,
        trigger=trigger,
        id="daily_intelligence_pipeline",
        name="Pipeline Diario 07:00 AM",
        replace_existing=True
    )
    scheduler.start()
    logger.info(f"Cron programado con APScheduler: todos los días a las {hour:02d}:{minute:02d} AM.")

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
    """Fuerza la ejecución inmediata del pipeline completo (End-to-End)."""
    result = await run_daily_pipeline()
    return result


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
