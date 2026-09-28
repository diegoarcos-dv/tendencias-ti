"""Script de prueba y verificación de la Fase 1."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.context_reader import business_context
from app.connectors import (
    ProductHuntConnector,
    RedditB2BConnector,
    GoogleTrendsConnector,
    fetch_all_trends,
)


def run_tests():
    print("=" * 60)
    print("EJECUTANDO TEST DE FASE 1: ORQUESTACIÓN Y FUENTES")
    print("=" * 60)

    # 1. Probar BusinessContextReader
    print("\n[1/4] Verificando Lector de Contexto de Negocio...")
    raw = business_context.raw_content
    assert len(raw) > 0, "El contenido de tendencias.txt está vacío"
    categories = business_context.categories
    print(f"  -> Contexto cargado: {len(raw)} caracteres")
    print(f"  -> Secciones detectadas: {list(categories.keys())}")
    print(f"  -> Keywords indexadas: {len(business_context.keywords)}")

    # Probar relevancia de ejemplo
    test_relevance_positive = business_context.is_relevant_to_business("Plataforma SaaS para optimización y analítica web B2B")
    test_relevance_negative = business_context.is_relevant_to_business("Receta de cocina con pasta casera")
    print(f"  -> Prueba afinidad Software/SaaS: {test_relevance_positive} (Esperado: True)")
    print(f"  -> Prueba afinidad no relacionada: {test_relevance_negative} (Esperado: False)")
    assert test_relevance_positive is True, "Fallo al detectar relevancia de afinidad de negocio"

    # 2. Probar Product Hunt Connector
    print("\n[2/4] Verificando Conector Product Hunt...")
    ph = ProductHuntConnector()
    ph_trends = ph.fetch_trends(limit=5)
    print(f"  -> Items obtenidos de Product Hunt: {len(ph_trends)}")
    if ph_trends:
        sample = ph_trends[0]
        print(f"     Ejemplo: [{sample.source}] {sample.title} | Score: {sample.metric_score} | Relevante: {sample.business_relevant}")
        print(f"     URL: {sample.url}")
    assert len(ph_trends) > 0, "No se obtuvieron items de Product Hunt"

    # 3. Probar Reddit B2B Connector
    print("\n[3/4] Verificando Conector Reddit B2B...")
    reddit = RedditB2BConnector(subreddits=["SaaS", "ecommerce"])
    reddit_trends = reddit.fetch_trends(limit_per_sub=3)
    print(f"  -> Items obtenidos de Reddit: {len(reddit_trends)}")
    if reddit_trends:
        sample = reddit_trends[0]
        print(f"     Ejemplo: [{sample.source}] {sample.title} | Categoria: {sample.category} | Relevante: {sample.business_relevant}")
        print(f"     URL: {sample.url}")
    assert len(reddit_trends) > 0, "No se obtuvieron items de Reddit"

    # 4. Probar Google Trends Connector
    print("\n[4/4] Verificando Conector Google Trends...")
    gt = GoogleTrendsConnector()
    gt_trends = gt.fetch_trends(limit=5)
    print(f"  -> Items obtenidos de Google Trends: {len(gt_trends)}")
    if gt_trends:
        sample = gt_trends[0]
        print(f"     Ejemplo: [{sample.source}] {sample.title} | Score: {sample.metric_score} | Relevante: {sample.business_relevant}")
        print(f"     URL: {sample.url}")
    assert len(gt_trends) > 0, "No se obtuvieron items de Google Trends"

    # 5. Ingesta Unificada
    print("\n[5/5] Probando Ingesta Global Unificada (fetch_all_trends)...")
    all_trends = fetch_all_trends()
    print(f"  -> Total de tendencias recolectadas: {len(all_trends)}")
    relevant_count = sum(1 for t in all_trends if t.business_relevant)
    print(f"  -> Tendencias relevantes al negocio identificadas: {relevant_count}/{len(all_trends)}")

    print("\n" + "=" * 60)
    print("TODAS LAS PRUEBAS DE LA FASE 1 FUERON EXITOSAS")
    print("=" * 60)


if __name__ == "__main__":
    run_tests()
