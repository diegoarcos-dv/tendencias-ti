"""Scoring Engine: Filtrado y selección de la Tendencia Top-1 del día.

Responsabilidades:
- Recibir la lista cruda de tendencias de los conectores.
- Descartar ítems ya registrados en historial_envios (deduplicación diaria).
- Calcular una puntuación compuesta basada en tracción y relevancia de negocio.
- Retornar únicamente la tendencia "Top 1" lista para ser procesada por el motor cognitivo.
"""

import logging
from typing import List, Optional

from app.connectors import TrendItem
from app.database import trend_exists, init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pesos del algoritmo de scoring compuesto
# ---------------------------------------------------------------------------
_WEIGHT_METRIC_SCORE = 0.50   # Tracción numérica (upvotes / tráfico / score)
_WEIGHT_BUSINESS_RELEVANCE = 0.35  # Coincidencia con la fuente de verdad del negocio
_WEIGHT_SOURCE_PRIORITY = 0.15  # Fuente con mayor señal de intención comercial

# Mayor puntaje de referencia para normalizar metric_score
_METRIC_NORMALIZER = 10_000.0

# Prioridad por fuente (0..1) — product_hunt tiene mayor intención comercial
_SOURCE_PRIORITY: dict[str, float] = {
    "product_hunt": 1.0,
    "reddit": 0.65,
    "google_trends": 0.45,
}


def _composite_score(item: TrendItem) -> float:
    """Calcula la puntuación compuesta de una tendencia (0.0 — 1.0+)."""
    # Normalizar métrica de tracción (capped en 1.0)
    normalised_metric = min(item.metric_score / _METRIC_NORMALIZER, 1.0)

    # Bono binario de relevancia de negocio
    relevance_bonus = 1.0 if item.business_relevant else 0.0

    # Prioridad de fuente
    source_priority = _SOURCE_PRIORITY.get(item.source, 0.3)

    score = (
        normalised_metric * _WEIGHT_METRIC_SCORE
        + relevance_bonus * _WEIGHT_BUSINESS_RELEVANCE
        + source_priority * _WEIGHT_SOURCE_PRIORITY
    )
    return round(score, 6)


def score_and_select(trends: List[TrendItem]) -> Optional[TrendItem]:
    """Filtra duplicados del historial diario y devuelve la tendencia Top-1.

    Args:
        trends: Lista cruda de TrendItem provenientes de fetch_all_trends().

    Returns:
        El TrendItem con mayor puntuación compuesta que aún no ha sido enviado hoy,
        o None si todas las tendencias ya fueron enviadas.
    """
    if not trends:
        logger.warning("[Scorer] Lista de tendencias vacía.")
        return None

    # Asegurar que la BD esté inicializada
    init_db()

    # ------------------------------------------------------------------ #
    # 1. Filtrar tendencias ya enviadas hoy (deduplicación diaria)         #
    # ------------------------------------------------------------------ #
    fresh = [t for t in trends if not trend_exists(t.url)]
    logger.info(
        f"[Scorer] {len(trends)} tendencias recibidas → "
        f"{len(fresh)} frescas después de filtrar historial."
    )

    if not fresh:
        logger.warning("[Scorer] Todas las tendencias del día ya fueron enviadas.")
        return None

    # ------------------------------------------------------------------ #
    # 2. Calcular puntuación compuesta y ordenar descendentemente          #
    # ------------------------------------------------------------------ #
    ranked = sorted(fresh, key=_composite_score, reverse=True)

    top = ranked[0]
    top_score = _composite_score(top)
    logger.info(
        f"[Scorer] Top-1 seleccionada → '{top.title}' "
        f"| fuente={top.source} | métrica={top.metric_score} "
        f"| relevante={top.business_relevant} | score_compuesto={top_score}"
    )

    return top
