"""Test integral de persistencia SQLite y filtro anti-duplicados (Punto 1).

Verifica:
1. Normalización de URLs (remoción de parámetros UTM y tracking).
2. Guardado en SQLite (radar.db) con card_data y normalized_title.
3. Detección de duplicados dentro de la ventana de cooldown (30 días).
4. Detección de duplicado por URL normalizada con diferentes parámetros de tracking.
5. Descarte automático de duplicados en el Scoring Engine (select_top_trend).
6. Recuperación por ID (get_trend_by_id) con deserialización de card_data.
7. Marcado y consulta de favoritos (mark_as_favorite, get_favorites).
"""

import sys
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import (
    init_db,
    save_trend,
    trend_exists,
    get_trend_by_id,
    get_favorites,
    mark_as_favorite,
    get_recent_sent_trends,
    _normalize_url,
    _normalize_title,
    _url_hash,
)
from app.connectors import TrendItem
from app.main import select_top_trend


def test_url_normalization():
    print("\n[1/6] Verificando normalización de URLs y títulos...")
    raw_url_1 = "https://ProductHunt.com/posts/agrotrack-iot/?utm_source=twitter&utm_medium=social"
    raw_url_2 = "https://producthunt.com/posts/agrotrack-iot?ref=producthunt"
    raw_url_3 = "https://producthunt.com/posts/agrotrack-iot"

    norm_1 = _normalize_url(raw_url_1)
    norm_2 = _normalize_url(raw_url_2)
    norm_3 = _normalize_url(raw_url_3)

    assert norm_1 == "https://producthunt.com/posts/agrotrack-iot", f"Fallo norm_1: {norm_1}"
    assert norm_2 == "https://producthunt.com/posts/agrotrack-iot", f"Fallo norm_2: {norm_2}"
    assert norm_3 == "https://producthunt.com/posts/agrotrack-iot", f"Fallo norm_3: {norm_3}"

    hash_1 = _url_hash(raw_url_1)
    hash_2 = _url_hash(raw_url_2)
    hash_3 = _url_hash(raw_url_3)

    assert hash_1 == hash_2 == hash_3, "Los hashes de URLs equivalentes deben ser idénticos tras normalización"
    print("  -> Hashes idénticos a pesar de variaciones UTM/tracking: OK")

    norm_t = _normalize_title("  ¡Plataforma IA de Analítica B2B (2026)!  ")
    assert norm_t == "plataformaiadeanaliticab2b2026"
    print("  -> Normalización de título insensible a caracteres especiales: OK")


def test_save_and_retrieve():
    print("\n[2/6] Verificando save_trend y get_trend_by_id con card_data...")
    trend_data = {
        "url": "https://producthunt.com/posts/saas-radar-pro",
        "title": "SaaS Radar Pro",
        "source": "product_hunt",
        "category": "TI & Software B2B",
        "metric_score": 950.0,
    }
    card_data = {
        "sector": "TI & Software B2B",
        "title": "SaaS Radar Pro",
        "metric_value": "45K+",
        "summary": "Plataforma de inteligencia de mercado B2B.",
    }

    trend_id = save_trend(trend_data, card_data=card_data)
    assert trend_id > 0, f"ID de tendencia inválido: {trend_id}"
    print(f"  -> Tendencia guardada con ID: {trend_id}")

    retrieved = get_trend_by_id(trend_id)
    assert retrieved is not None, "get_trend_by_id retornó None"
    assert retrieved["title"] == "SaaS Radar Pro"
    assert retrieved["card_data"] is not None
    assert retrieved["card_data"]["metric_value"] == "45K+"
    print("  -> Recuperación y deserialización de card_data: OK")


def test_anti_duplication_detection():
    print("\n[3/6] Verificando detección de duplicados con ventana de cooldown...")
    base_url = "https://producthunt.com/posts/saas-radar-pro"

    # Con la misma URL exacta
    assert trend_exists(base_url, days_cooldown=30) is True

    # Con parámetros de tracking diferentes
    dirty_url = "https://producthunt.com/posts/saas-radar-pro?utm_campaign=launch&ref=hackernews"
    assert trend_exists(dirty_url, days_cooldown=30) is True
    print("  -> Detección de duplicado por URL con tracking params: OK")

    # Por título coincidente
    assert trend_exists("https://otra-url.com/xyz", title="SaaS Radar Pro", days_cooldown=30) is True
    print("  -> Detección secundaria por título: OK")

    # URL completamente nueva
    assert trend_exists("https://otra-url-completamente-nueva.org/item-123", days_cooldown=30) is False
    print("  -> URL no registrada retorna False correctamente: OK")


def test_scorer_deduplication_filtering():
    print("\n[4/6] Verificando descarte automático de duplicados en el Scoring Engine...")

    # Guardar una tendencia conocida
    already_sent_url = "https://producthunt.com/posts/sistema-erp-financiero"
    save_trend({
        "url": already_sent_url,
        "title": "Sistema ERP Financiero",
        "source": "product_hunt",
        "category": "FinTech",
        "metric_score": 9999.0,
    })

    # Crear lista con:
    # 1. La tendencia que ya se envió (tiene altísimo score pero DEBE descartarse)
    # 2. Una tendencia fresca con buen score (DEBE ser la ganadora)
    # 3. Otra tendencia fresca con menor score
    mock_candidates = [
        TrendItem(
            title="Sistema ERP Financiero (Ya enviado)",
            url=already_sent_url,
            source="product_hunt",
            category="FinTech",
            metric_score=9999.0,
            business_relevant=True,
            summary="Resumen repetido",
            timestamp=datetime.now(timezone.utc),
        ),
        TrendItem(
            title="FreshTech Logistics AI (Ganadora Fresca)",
            url="https://producthunt.com/posts/freshtech-logistics-ai",
            source="product_hunt",
            category="E-Commerce Logistics",
            metric_score=1200.0,
            business_relevant=True,
            summary="Resumen fresca 1",
            timestamp=datetime.now(timezone.utc),
        ),
        TrendItem(
            title="Small Utility Tool (Menor Score)",
            url="https://producthunt.com/posts/small-tool",
            source="product_hunt",
            category="TI",
            metric_score=100.0,
            business_relevant=False,
            summary="Resumen fresca 2",
            timestamp=datetime.now(timezone.utc),
        ),
    ]

    top_selected = select_top_trend(mock_candidates, days_cooldown=30)
    assert top_selected is not None, "El Scorer no seleccionó ninguna tendencia"
    assert top_selected.title == "FreshTech Logistics AI (Ganadora Fresca)", (
        f"Se seleccionó incorrectamente: '{top_selected.title}'. El duplicado debió ser descartado."
    )
    print(f"  -> Duplicado ignorado y seleccionada la mejor tendencia fresca: '{top_selected.title}' [OK]")


def test_favorites_and_history():
    print("\n[5/6] Verificando favoritos y listado de historial...")
    recent = get_recent_sent_trends(limit=5)
    assert len(recent) >= 2, f"Se esperaban al menos 2 registros en historial, se obtuvieron {len(recent)}"
    target_id = recent[0]["id"]

    success = mark_as_favorite(target_id)
    assert success is True, "mark_as_favorite falló"

    favs = get_favorites()
    assert len(favs) >= 1, "get_favorites retornó lista vacía"
    print(f"  -> Favorito guardado con éxito. Total favoritos: {len(favs)} [OK]")


def test_api_routes():
    print("\n[6/6] Verificando endpoints FastAPI de Historial y Favoritos...")
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    # 2. History endpoint
    res_hist = client.get("/api/v1/history?limit=10")
    assert res_hist.status_code == 200
    data_hist = res_hist.json()
    assert "total" in data_hist
    assert "trends" in data_hist
    assert data_hist["total"] >= 2
    print(f"  -> GET /api/v1/history: 200 OK ({data_hist['total']} registros)")

    # 3. Favorites endpoint
    res_fav = client.get("/api/v1/favorites")
    assert res_fav.status_code == 200
    data_fav = res_fav.json()
    assert "total" in data_fav
    assert "favorites" in data_fav
    print(f"  -> GET /api/v1/favorites: 200 OK ({data_fav['total']} favoritos)")


if __name__ == "__main__":
    print("=" * 65)
    print("EJECUTANDO TEST DE PERSISTENCIA Y FILTRO ANTI-DUPLICADOS")
    print("=" * 65)
    test_url_normalization()
    test_save_and_retrieve()
    test_anti_duplication_detection()
    test_scorer_deduplication_filtering()
    test_favorites_and_history()
    test_api_routes()
    print("\n" + "=" * 65)
    print("¡TODAS LAS PRUEBAS DE PERSISTENCIA Y ANTI-DUPLICADOS PASARON!")
    print("=" * 65)
