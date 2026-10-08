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
import sys
import logging

# Configuración obligatoria en Windows para soporte nativo de subprocesos y Playwright
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass


def proactor_loop_factory(*args, **kwargs):
    """Factory de bucle para Uvicorn en Windows: garantiza ProactorEventLoop y elimina NotImplementedError."""
    if sys.platform == "win32":
        return lambda: asyncio.ProactorEventLoop()
    return lambda: asyncio.new_event_loop()


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
    get_user_zone_hierarchy,
    get_user_zones,
    get_user_industry,
    get_user_exact_industry,
    get_user_categoria_api,
    get_user_daily_card_count,
    get_expired_card_messages,
    delete_card_record,
    get_all_configured_users,
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
    clear_chart_cache,
)

from app.logger import setup_logging

setup_logging()
logger = logging.getLogger("app.main")

# Instancia global del Scheduler asíncrono
scheduler = AsyncIOScheduler()


# ============================================================================
# Scoring Engine
# ============================================================================

def select_top_trend(
    trends: List[TrendItem],
    days_cooldown: Optional[int] = None,
    industry: Optional[str] = None
) -> Optional[TrendItem]:
    """Scoring Engine: Selecciona la herramienta o solución técnica 'Top 1' del día.

    Aplica:
    1. Filtro estricto anti-duplicados (descarta tendencias ya enviadas en la ventana de cooldown).
    2. Afinidad temática estricta con la fuente de verdad del negocio y perfil de industria.
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
        f"Frescas disponibles: {len(fresh_trends)} | Industria: {industry or 'Global/General'}"
    )

    if not fresh_trends:
        logger.warning(
            f"[Scoring Engine] Todas las tendencias candidatas ({len(trends)}) ya fueron enviadas en los últimos {cooldown} días."
        )
        return None

    def calculate_tool_score(item: TrendItem) -> float:
        # Relevancia con el archivo de negocio
        affinity_score = 5000.0 if item.business_relevant else 0.0

        # Afinidad con la industria personalizada del usuario
        industry_bonus = 0.0
        if industry and industry.lower() not in ("global", "ti & software b2b"):
            ind_words = [w.lower() for w in industry.replace("&", " ").split() if len(w) > 3]
            item_text = f"{item.title} {item.summary} {item.category}".lower()
            if any(w in item_text for w in ind_words):
                industry_bonus = 3000.0
        
        # Ponderación decisiva por especificidad de producto/herramienta de software concreta
        tool_bonus = 0.0
        if item.source == "product_hunt":
            tool_bonus = 2500.0  # Productos de software lanzados al mercado con servicios específicos
        elif item.source == "reddit":
            tool_bonus = 1500.0  # Soluciones y discusiones técnicas B2B de desarrolladores

        # Tracción cuantitativa real
        normalized_traction = min(item.metric_score, 1000.0)

        return affinity_score + industry_bonus + tool_bonus + normalized_traction

    sorted_trends = sorted(fresh_trends, key=calculate_tool_score, reverse=True)
    top_1 = sorted_trends[0]
    logger.info(
        f"Top 1 seleccionado por el Scoring Engine: '{top_1.title}' "
        f"[Fuente: {top_1.source}, Métrica: {top_1.metric_score}, Relevante: {top_1.business_relevant}]"
    )
    return top_1


def select_top_trends(
    trends: List[TrendItem],
    count: int = 5,
    days_cooldown: Optional[int] = None,
    industry: Optional[str] = None
) -> List[TrendItem]:
    """Scoring Engine: Selecciona el lote Top 3 a 5 de tendencias del día para el Catálogo Interactivo."""
    if not trends:
        return []
    init_db()
    cooldown = days_cooldown if days_cooldown is not None else settings.DEDUPLICATION_WINDOW_DAYS
    fresh_trends: List[TrendItem] = []
    for item in trends:
        if not trend_exists(url=item.url, title=item.title, days_cooldown=cooldown):
            fresh_trends.append(item)

    if not fresh_trends:
        fresh_trends = trends

    def calculate_tool_score(item: TrendItem) -> float:
        affinity_score = 5000.0 if item.business_relevant else 0.0
        industry_bonus = 0.0
        if industry and industry.lower() not in ("global", "ti & software b2b"):
            ind_words = [w.lower() for w in industry.replace("&", " ").split() if len(w) > 3]
            item_text = f"{item.title} {item.summary} {item.category}".lower()
            if any(w in item_text for w in ind_words):
                industry_bonus = 3000.0
        tool_bonus = 0.0
        if item.source == "product_hunt":
            tool_bonus = 2500.0
        elif item.source == "reddit":
            tool_bonus = 1500.0
        normalized_traction = min(item.metric_score, 1000.0)
        return affinity_score + industry_bonus + tool_bonus + normalized_traction

    sorted_trends = sorted(fresh_trends, key=calculate_tool_score, reverse=True)
    target_count = max(3, min(count, 5))

    # Asegurar diversidad temática: no repetir títulos similares o del mismo nicho exacto
    chosen: List[TrendItem] = []
    seen_titles: set = set()
    for item in sorted_trends:
        norm_t = item.title.strip().lower()
        if any(norm_t in s or s in norm_t for s in seen_titles):
            continue
        chosen.append(item)
        seen_titles.add(norm_t)
        if len(chosen) >= target_count:
            break

    if len(chosen) < target_count:
        for item in sorted_trends:
            if item not in chosen:
                chosen.append(item)
                if len(chosen) >= target_count:
                    break

    return chosen


# ============================================================================
# Pipelines: Grupo Público vs. Chat Privado (DM) y Caducidad TTL
# ============================================================================

async def run_group_pipeline(chat_id: Optional[str] = None) -> Dict[str, Any]:
    """1. Pipeline de Grupo: Publica el Catálogo Interactivo de 3 a 5 Tendencias con navegación in-situ."""
    target_chat = chat_id or settings.TELEGRAM_GROUP_CHAT_ID
    start_time = datetime.now()
    clear_chart_cache()
    logger.info("=" * 60)
    logger.info(f"[Pipeline Grupo] INICIO Catálogo Interactivo [{start_time.strftime('%H:%M:%S')}] -> Chat: {target_chat}")
    logger.info("=" * 60)

    # 1. Ingesta estricta de TI & Software B2B para el grupo corporativo y selección de 3 a 5 tendencias diversas
    all_trends = fetch_all_trends(
        zone="Global",
        industry="TI & Software B2B",
        categoria_api="tech",
        industria_exacta="TI & Software B2B"
    )
    catalog_trends = select_top_trends(all_trends, count=5, industry="TI & Software B2B")
    if not catalog_trends:
        single = select_top_trend(all_trends)
        catalog_trends = [single] if single else []

    if not catalog_trends:
        logger.error("[Pipeline Grupo] No hay tendencias frescas disponibles para el catálogo.")
        return {"status": "error", "message": "No fresh trends available"}

    # 2. Análisis con Gemma, persistencia y pre-renderizado del lote completo
    saved_catalog = []
    first_png = None
    for idx, trend_item in enumerate(catalog_trends):
        trend_dict = {**trend_item.model_dump(), "geo_region": "Global"}
        card_data = await generate_trend_card_data(
            trend_data=trend_dict,
            zona_preferida="Global",
            user_industry=trend_item.category or "TI & Software B2B",
            business_context_text=business_context.raw_content
        )
        t_id = save_trend(trend_data=trend_item.model_dump(), card_data=card_data)
        trend_png = settings.BASE_DIR / f"temp_trend_{t_id}.png"
        await create_png_card(data=card_data, output_path=trend_png)
        if idx == 0:
            first_png = trend_png
        saved_catalog.append({"id": t_id, "trend": trend_item, "card_data": card_data, "png": trend_png})

    # Pre-renderizar tarjetas auxiliares (Demanda B2B, Eventos CDMX, Gráfica) para navegación instantánea
    try:
        from app.b2b_demand import get_b2b_demand_by_index
        from app.events_cdmx import get_events_cdmx_by_index
        from app.visual_engine import create_b2b_demand_png_card, create_events_cdmx_png_card, create_chart_png_card

        demand_png = settings.BASE_DIR / "temp_demand_0.png"
        await create_b2b_demand_png_card(output_path=demand_png, data=get_b2b_demand_by_index(0))

        events_png = settings.BASE_DIR / "temp_events_0.png"
        await create_events_cdmx_png_card(output_path=events_png, data=get_events_cdmx_by_index(0))

        chart_png = settings.BASE_DIR / "temp_chart.png"
        await create_chart_png_card(output_path=chart_png)
        logger.info("[Pipeline Grupo] Catálogos auxiliares (Empresas Demandantes, Calendario Eventos Jóvenes, Gráfica) pre-renderizados con éxito.")
    except Exception as ex_aux:
        logger.warning(f"[Pipeline Grupo] Advertencia al pre-renderizar catálogos auxiliares: {ex_aux}")

    # 3. Envío al grupo del primer elemento configurado con el Catálogo Interactivo
    first_item = saved_catalog[0]
    first_trend_id = first_item["id"]
    from app.telegram_bot import build_catalog_keyboard, set_catalog_cached_file_id
    catalog_markup = build_catalog_keyboard(current_index=0, total_items=len(saved_catalog), trend_id=first_trend_id)
    telegram_result = await send_telegram_notification(
        photo_path=first_png or (settings.BASE_DIR / "temp_group_card.png"),
        caption="",
        reply_markup=catalog_markup,
        chat_id=target_chat,
        chat_type="group",
        trend_id=first_trend_id
    )

    if telegram_result.get("file_id"):
        set_catalog_cached_file_id(f"trend_{first_trend_id}", telegram_result["file_id"])

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"[Pipeline Grupo] Éxito: Catálogo ({len(saved_catalog)} tendencias) enviado a {target_chat} en {duration:.2f}s")
    return {
        "status": "success",
        "chat_type": "group",
        "chat_id": target_chat,
        "catalog_size": len(saved_catalog),
        "first_trend_id": first_trend_id,
        "duration_seconds": duration,
        "telegram_result": telegram_result
    }


async def run_individual_pipeline(chat_id: Optional[str] = None, ignore_daily_limit: bool = False) -> Dict[str, Any]:
    """2. Pipeline Individual (DM): Segmentado por la zona del usuario, menú completo de 4 botones.
    Respeta el límite estricto de 3 envíos diarios por usuario.
    """
    target_chat = chat_id or settings.TELEGRAM_CHAT_ID
    start_time = datetime.now()

    # Verificar límite estricto de 3 envíos diarios por usuario
    daily_count = get_user_daily_card_count(str(target_chat))
    max_daily = settings.USER_DAILY_SEND_LIMIT
    if not ignore_daily_limit and daily_count >= max_daily:
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
    logger.info(f"[Pipeline Individual] INICIO ciclo -> Chat: {target_chat} (Envío {daily_count + 1}/{max_daily})")
    logger.info("=" * 60)
    clear_chart_cache()

    # 1. Obtener preferencias multizona e industria del usuario
    user_zones = get_user_zones(str(target_chat))
    user_industry = get_user_industry(str(target_chat)) or "TI & Software B2B"
    user_exact_industry = get_user_exact_industry(str(target_chat)) or user_industry
    user_categoria_api = get_user_categoria_api(str(target_chat)) or "general"

    top_trend = None
    fallback_activado = False
    chosen_zone_local = ""
    selected_candidates: List[TrendItem] = []
    fallback_activado = False
    chosen_zone_local = ""
    chosen_zone_pais = ""
    effective_zone = ""

    # Iterar sobre la lista de zonas configuradas del usuario:
    for z_entry in user_zones:
        cur_local = str(z_entry.get("zona_local") or "").strip() or "Global"
        cur_pais = str(z_entry.get("zona_pais") or "").strip() or cur_local

        logger.info(f"[Pipeline Individual] Buscando lote de tendencias para '{user_exact_industry}' en zona: '{cur_local}'...")
        all_trends = fetch_all_trends(
            zone=cur_local,
            industry=user_exact_industry,
            categoria_api=user_categoria_api,
            industria_exacta=user_exact_industry
        )
        cands = select_top_trends(all_trends, count=4, industry=user_exact_industry)
        if not cands:
            single = select_top_trend(all_trends, industry=user_exact_industry)
            cands = [single] if single else []

        cur_fallback = False
        # Búsqueda con Rescate si la zona local no arrojó resultados y difiere del país macro:
        if not cands and cur_local.strip().lower() != cur_pais.strip().lower():
            logger.warning(
                f"[Pipeline Individual] 0 tendencias encontradas para '{cur_local}'. "
                f"Ejecutando búsqueda de rescate ampliada a nivel país macro: '{cur_pais}'..."
            )
            rescue_trends = fetch_all_trends(
                zone=cur_pais,
                industry=user_exact_industry,
                categoria_api=user_categoria_api,
                industria_exacta=user_exact_industry
            )
            cands = select_top_trends(rescue_trends, count=4, industry=user_exact_industry)
            if not cands:
                single_r = select_top_trend(rescue_trends, industry=user_exact_industry)
                cands = [single_r] if single_r else []
            if cands:
                cur_fallback = True
                logger.info(
                    f"[Pipeline Individual] Búsqueda de rescate exitosa ({len(cands)} tendencias) en '{cur_pais}' para '{user_exact_industry}'."
                )

        if cands:
            selected_candidates = cands
            fallback_activado = cur_fallback
            chosen_zone_local = cur_local
            chosen_zone_pais = cur_pais
            effective_zone = cur_pais if cur_fallback else cur_local
            logger.info(
                f"[Pipeline Individual] Lote de {len(cands)} tendencias válidas encontradas en '{effective_zone}'. "
                f"Deteniendo iteración multizona para proceder al envío del carrusel."
            )
            break

    if not selected_candidates:
        logger.error(
            f"[Pipeline Individual] No hay tendencias frescas disponibles para {user_exact_industry} "
            f"en ninguna de las zonas configuradas: {[z.get('zona_local') for z in user_zones]}."
        )
        return {"status": "error", "message": "No fresh trends available"}

    # 2. Análisis con Gemma, renderizado con Playwright y persistencia del lote de tendencias (3 a 5)
    saved_catalog = []
    first_png = None
    first_trend_id = None
    first_candidate = selected_candidates[0]

    for idx, cand in enumerate(selected_candidates):
        trend_dict = {
            **cand.model_dump(),
            "geo_region": effective_zone,
            "category": user_exact_industry,
            "industria_exacta": user_exact_industry,
            "fallback_activado": fallback_activado,
            "zona_local": chosen_zone_local,
            "zona_pais": chosen_zone_pais
        }
        card_data = await generate_trend_card_data(
            trend_data=trend_dict,
            zona_preferida=effective_zone,
            user_industry=user_exact_industry,
            business_context_text=business_context.raw_content
        )
        card_data["fallback_activado"] = fallback_activado
        card_data["zona_local"] = chosen_zone_local
        card_data["zona_pais"] = chosen_zone_pais

        t_id = save_trend(trend_data=cand.model_dump(), card_data=card_data)
        trend_png = settings.BASE_DIR / f"temp_trend_{t_id}.png"
        await create_png_card(data=card_data, output_path=trend_png)

        if idx == 0:
            first_png = trend_png
            first_trend_id = t_id

        saved_catalog.append({"id": t_id, "trend": cand, "card_data": card_data, "png": trend_png})

    # Registrar el catálogo en memoria para la navegación interactiva fluida (◀️ / ▶️)
    from app.telegram_bot import set_cached_catalog_trends
    set_cached_catalog_trends(saved_catalog)

    # 3. Notificación y Envío del primer elemento del carrusel a Telegram
    caption = ""
    if fallback_activado:
        caption = f"📍 *Nota del radar: No detectamos volumen suficiente de datos en {chosen_zone_local} hoy, por lo que hemos ampliado el análisis a nivel {chosen_zone_pais}.*"

    reply_markup = build_interactive_keyboard(
        trend_id=first_trend_id,
        source_url=first_candidate.url,
        current_index=0,
        total_items=len(saved_catalog)
    )
    telegram_result = await send_telegram_notification(
        photo_path=first_png or (settings.BASE_DIR / "temp_card.png"),
        caption=caption,
        parse_mode="Markdown" if fallback_activado else "HTML",
        reply_markup=reply_markup,
        chat_id=target_chat,
        chat_type="private",
        trend_id=first_trend_id,
        fallback_activado=fallback_activado,
        zona_local=chosen_zone_local,
        zona_pais=chosen_zone_pais
    )

    duration = (datetime.now() - start_time).total_seconds()
    logger.info(
        f"[Pipeline Individual] Éxito: Carrusel ({len(saved_catalog)} tendencias) enviado a {target_chat} "
        f"(trend_id={first_trend_id}) en {duration:.2f}s | Zona: {effective_zone} | Industria: {user_industry}"
    )
    return {
        "status": "success",
        "chat_type": "private",
        "chat_id": target_chat,
        "zone": effective_zone,
        "zona_local": chosen_zone_local,
        "zona_pais": chosen_zone_pais,
        "fallback_activado": fallback_activado,
        "industry": user_industry,
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


async def run_all_individual_pipelines() -> Dict[str, Any]:
    """Tarea programada diaria a las 10:00 AM para chats individuales (DM):
    Consulta en SQLite a todos los usuarios con perfil completo (zona e industria definidas),
    detona la búsqueda personalizada de forma asíncrona con Gemma y entrega la tarjeta visual a sus chat_id privados.
    """
    start_time = datetime.now()
    configured_users = get_all_configured_users()

    # Si no hay usuarios en la tabla pero está configurado TELEGRAM_CHAT_ID como admin/default:
    if not configured_users and settings.TELEGRAM_CHAT_ID:
        configured_users = [{"chat_id": str(settings.TELEGRAM_CHAT_ID), "zona_preferida": "Global", "industria": "TI & Software B2B"}]

    logger.info(f"[Cron 10:00 AM] Iniciando envío de radar individual para {len(configured_users)} usuarios con perfil completo.")

    dispatched = []
    for user in configured_users:
        cid = str(user["chat_id"])
        # Detonar la búsqueda personalizada y envío asíncrono para cada usuario
        asyncio.create_task(run_individual_pipeline(chat_id=cid))
        dispatched.append(cid)

    duration = (datetime.now() - start_time).total_seconds()
    return {
        "status": "success",
        "job": "individual_daily_10am",
        "total_users": len(configured_users),
        "dispatched_chat_ids": dispatched,
        "dispatch_duration_seconds": duration
    }


async def run_hourly_scheduled_individual_pipelines() -> None:
    """Dispatcher horario: revisa si hay usuarios cuyo schedule_time coincida con la hora actual."""
    now_hh_mm = datetime.now().strftime("%H:00")
    from app.database import get_users_by_schedule
    users = get_users_by_schedule(now_hh_mm)
    if users:
        logger.info(f"[Dispatcher Horario {now_hh_mm}] Despachando tendencias para {len(users)} usuarios programados a esta hora.")
        for u in users:
            cid = u.get("chat_id")
            if cid:
                asyncio.create_task(run_individual_pipeline(chat_id=cid, ignore_daily_limit=True))


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

    # 1. Cronograma del Grupo Público: Catálogo Diario a las 10:00 AM
    scheduler.add_job(
        run_group_pipeline,
        trigger=CronTrigger(hour=10, minute=0),
        id="group_intelligence_catalog_daily_10am",
        name="Catálogo Diario Grupo TI (10:00 AM)",
        replace_existing=True,
        misfire_grace_time=3600
    )
    logger.info("Cron de Grupo programado: Catálogo interactivo diario a las 10:00 AM.")

    # 2. Cronograma de Notificaciones Individuales (DMs): Todos los días a las 10:00 AM
    scheduler.add_job(
        run_all_individual_pipelines,
        trigger=CronTrigger(hour=10, minute=0),
        id="individual_intelligence_pipeline_daily_10am",
        name="Pipeline Individual Diario (10:00 AM)",
        replace_existing=True,
        misfire_grace_time=3600
    )
    logger.info("Cron Individual programado: diariamente a las 10:00 AM para todos los usuarios con perfil completo.")

    # 3. Tarea Diaria de Caducidad de Mensajes (TTL 7 Días): Corre a las 03:00 AM
    scheduler.add_job(
        cleanup_expired_messages,
        trigger=CronTrigger(hour=3, minute=0),
        id="cleanup_expired_cards_daily",
        name="Depuración Diaria TTL Tarjetas 7 Días (03:00 AM)",
        replace_existing=True,
        misfire_grace_time=3600
    )
    logger.info("Cron de Caducidad (TTL 7 días) programado: diariamente a las 03:00 AM.")

    # 4. Dispatcher Horario para entregas personalizadas por usuario: Cada hora
    scheduler.add_job(
        run_hourly_scheduled_individual_pipelines,
        trigger=CronTrigger(minute=0),
        id="individual_hourly_dispatcher",
        name="Dispatcher Horario de Notificaciones Individuales (Cada Hora)",
        replace_existing=True,
        misfire_grace_time=1800
    )
    logger.info("Dispatcher Horario activo: monitorea las horas configuradas por cada usuario cada hora.")

    scheduler.start()

    yield

    logger.info("Deteniendo Long Polling de Telegram, APScheduler, Navegador Caliente y Cliente HTTP...")
    await stop_bot_polling()
    from app.visual_engine import close_browser_singleton
    await close_browser_singleton()
    from app.llm_service import close_http_client
    await close_http_client()
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
    """Fuerza la ejecución del pipeline individual (Enfoque por zona; para un chat específico o para todos los configurados)."""
    if chat_id:
        return await run_individual_pipeline(chat_id=chat_id)
    return await run_all_individual_pipelines()


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
