"""Test de integración de la Fase 2: Memoria, Filtrado y Motor Cognitivo.

Valida el pipeline completo:
  tendencia cruda → scorer (SQLite) → Top-1 → LLM → JSON estructurado

Nota sobre LLM: si Ollama no está disponible, el test de motor cognitivo se
ejecuta en modo MOCK (inyectando un JSON sintético) para validar la lógica
de parseo y el contrato de datos sin depender de hardware externo.
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.connectors import TrendItem
from app.database import init_db, save_trend, trend_exists, mark_as_favorite, get_favorites, get_daily_history, DB_PATH
from app.scorer import score_and_select
from app.llm_service import analyze_trend_impact, check_ollama_health, _extract_json


# ---------------------------------------------------------------------------
# Tendencias de prueba sintéticas
# ---------------------------------------------------------------------------

def _make_trend(title: str, url: str, source: str = "product_hunt",
                score: float = 500.0, relevant: bool = True) -> TrendItem:
    return TrendItem(
        title=title,
        source=source,
        category="TI & B2B SaaS",
        url=url,
        summary=f"Resumen de prueba para {title}",
        metric_score=score,
        business_relevant=relevant,
        timestamp=datetime.now(timezone.utc),
    )


MOCK_TRENDS = [
    _make_trend("CloudSec Pro — Observabilidad y Ciberseguridad B2B",
                "https://producthunt.com/posts/cloudsec-pro", score=1200.0),
    _make_trend("SaaSMetrics Pro — BI Comercial Autónomo",
                "https://producthunt.com/posts/saas-metrics-pro", score=900.0),
    _make_trend("Receta de pasta casera",                               # No relevante
                "https://reddit.com/r/cooking/pasta", source="reddit",
                score=50.0, relevant=False),
    _make_trend("EcomLogix — Logística Última Milla con ML",
                "https://reddit.com/r/ecommerce/ecomlogix", source="reddit",
                score=650.0),
]

MOCK_LLM_RESPONSE = json.dumps({
    "titulo": "CloudSec Pro — Observabilidad y Ciberseguridad B2B",
    "categoria": "Ciberseguridad & Cloud",
    "impacto_comercial": (
        "La observabilidad proactiva de infraestructura reduce incidentes operativos "
        "hasta un 30% y habilita cumplimiento de normativas de seguridad de datos. "
        "Compatible con arquitecturas cloud y microservicios modernos."
    ),
    "nivel_viabilidad": "Alta",
    "roi_estimado": "Recuperación de inversión en 4-5 meses con mitigación de brechas de seguridad.",
    "plan_de_accion": [
        "Despliegue de agentes ligeros en clusters de prueba para validar telemetría.",
        "Integración con paneles de observabilidad y alertas de anomalías en tiempo real.",
        "Escalamiento a toda la infraestructura e implementación de políticas de acceso cero confianza.",
    ],
    "fuente": "https://producthunt.com/posts/cloudsec-pro",
    "puntuacion_relevancia": 1200.0,
}, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_1_database_init_and_tables():
    """[1/5] La BD se inicializa correctamente y ambas tablas existen."""
    print("\n[1/5] Verificando inicialización de la base de datos SQLite...")
    init_db()
    assert DB_PATH.exists(), f"El archivo de BD no fue creado en {DB_PATH}"

    import sqlite3
    with sqlite3.connect(str(DB_PATH)) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}

    assert "historial_envios" in tables, "Falta la tabla historial_envios"
    assert "tendencias_guardadas" in tables, "Falta la tabla tendencias_guardadas"
    print(f"  -> BD creada en: {DB_PATH}")
    print(f"  -> Tablas detectadas: {tables}")
    print("  [OK]")


def test_2_save_and_dedup():
    """[2/5] save_trend persiste, trend_exists detecta duplicados del día."""
    print("\n[2/5] Verificando save_trend y deduplicación diaria...")
    trend_dict = MOCK_TRENDS[0].model_dump()
    # Convertir datetime a string para la función
    trend_dict["timestamp"] = trend_dict["timestamp"].isoformat()

    trend_id = save_trend(trend_dict)
    assert trend_id > 0, "save_trend debe retornar un ID positivo"
    print(f"  -> Tendencia guardada con ID: {trend_id}")

    # Debe existir ahora
    exists = trend_exists(MOCK_TRENDS[0].url)
    assert exists is True, "trend_exists debe retornar True para una URL recién guardada"
    print(f"  -> Deduplicación detectada correctamente: trend_exists = {exists}")

    # URL desconocida no debe existir
    not_exists = trend_exists("https://tendencia-que-nunca-existio.com/xyz")
    assert not_exists is False, "trend_exists debe retornar False para URL nueva"
    print(f"  -> URL nueva correctamente marcada como nueva: trend_exists = {not_exists}")
    print("  [OK]")


def test_3_favorites():
    """[3/5] mark_as_favorite y get_favorites funcionan correctamente."""
    print("\n[3/5] Verificando favoritos...")
    # El ID 1 fue guardado en test_2
    result = mark_as_favorite(1)
    assert result is True, "mark_as_favorite debe retornar True para ID existente"

    favs = get_favorites()
    assert len(favs) >= 1, "get_favorites debe retornar al menos un favorito"
    print(f"  -> Favoritos guardados: {len(favs)}")
    print(f"  -> Título del favorito: {favs[0]['title']}")
    print("  [OK]")


def test_4_scorer_pipeline():
    """[4/5] El Scorer filtra duplicados y devuelve el Top-1 correcto."""
    print("\n[4/5] Verificando Scoring Engine...")

    # MOCK_TRENDS[0] ya fue enviado hoy (test_2); debe ser excluido.
    # El Top-1 esperado es MOCK_TRENDS[1] (score 900, product_hunt, relevante).
    # Pero como no tenemos certeza del estado previo de BD en CI, usamos URLs frescas.

    fresh_trends = [
        _make_trend("FreshTrend Alpha", "https://fresh.test/alpha",
                    source="product_hunt", score=800.0, relevant=True),
        _make_trend("FreshTrend Beta", "https://fresh.test/beta",
                    source="reddit", score=1500.0, relevant=False),
        _make_trend("FreshTrend Gamma", "https://fresh.test/gamma",
                    source="product_hunt", score=900.0, relevant=True),
    ]

    top = score_and_select(fresh_trends)

    assert top is not None, "score_and_select no debe retornar None con tendencias frescas"
    print(f"  -> Top-1 seleccionada: '{top.title}'")
    print(f"     source={top.source} | score={top.metric_score} | relevant={top.business_relevant}")

    # Gamma tiene mejor puntuación compuesta (product_hunt + relevante + score 900)
    assert top.title == "FreshTrend Gamma", (
        f"El Top-1 esperado es 'FreshTrend Gamma' pero se obtuvo '{top.title}'"
    )

    # Correr scorer sobre lista vacía → None
    assert score_and_select([]) is None, "Lista vacía debe retornar None"
    print("  [OK]")


async def test_5_llm_analysis_mock():
    """[5/5] analyze_trend_impact parsea y enriquece correctamente la respuesta del LLM."""
    print("\n[5/5] Verificando Motor Cognitivo (Ollama mock)...")

    trend_dict = MOCK_TRENDS[0].model_dump()
    trend_dict["timestamp"] = trend_dict["timestamp"].isoformat()

    ollama_online = await check_ollama_health()
    print(f"  -> Ollama disponible: {ollama_online}")

    if ollama_online:
        print("  -> Modo REAL: enviando tendencia a Ollama/Gemma...")
        result = await analyze_trend_impact(trend_dict)
    else:
        print("  -> Modo MOCK: Ollama no disponible, inyectando respuesta sintética...")
        with patch("app.llm_service._call_ollama", new=AsyncMock(return_value=MOCK_LLM_RESPONSE)):
            result = await analyze_trend_impact(trend_dict)

    # Verificar contrato de datos
    required_keys = ["titulo", "categoria", "impacto_comercial",
                     "nivel_viabilidad", "plan_de_accion", "fuente"]
    for key in required_keys:
        assert key in result, f"El resultado del LLM debe contener la clave '{key}'"

    assert isinstance(result["plan_de_accion"], list), "plan_de_accion debe ser una lista"
    assert len(result["plan_de_accion"]) >= 1, "plan_de_accion debe tener al menos 1 paso"

    print(f"  -> Título del análisis: {result['titulo']}")
    print(f"  -> Categoría detectada: {result['categoria']}")
    print(f"  -> Viabilidad: {result['nivel_viabilidad']}")
    print(f"  -> Plan de acción ({len(result['plan_de_accion'])} pasos):")
    for i, step in enumerate(result["plan_de_accion"], 1):
        print(f"       {i}. {step}")
    print(f"\n  -> JSON estructurado completo:\n{json.dumps(result, ensure_ascii=False, indent=2)}")
    print("  [OK]")


def test_5_llm_json_extractor():
    """[5b] _extract_json maneja respuestas con texto envolvente."""
    print("\n[5b] Verificando extractor de JSON robusto...")
    wrapped = "Aquí tienes el análisis:\n```\n" + MOCK_LLM_RESPONSE + "\n```\n"
    result = _extract_json(wrapped)
    assert "titulo" in result, "No se pudo extraer JSON de respuesta con texto envolvente"
    print("  -> Parseo de JSON envuelto en texto: OK")
    print("  [OK]")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_tests():
    print("=" * 65)
    print("EJECUTANDO TEST DE FASE 2: MEMORIA, FILTRADO Y MOTOR COGNITIVO")
    print("=" * 65)

    init_db()  # Asegurar BD lista antes de todos los tests

    test_1_database_init_and_tables()
    test_2_save_and_dedup()
    test_3_favorites()
    test_4_scorer_pipeline()
    asyncio.run(test_5_llm_analysis_mock())
    test_5_llm_json_extractor()

    print("\n" + "=" * 65)
    print("[PASS]  TODAS LAS PRUEBAS DE LA FASE 2 FUERON EXITOSAS")
    print("    Pipeline: tendencia cruda -> scorer -> SQLite -> JSON estructurado")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
