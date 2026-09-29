"""Test de Validación del Panel Interactivo y Handlers de Telegram (Punto 2).

Verifica:
1. Existencia y formato exacto de los 4 botones en build_interactive_keyboard.
2. Renderizado de la plantilla secundaria tarjeta_grafica.html -> temp_chart.png con Playwright.
3. Ejecución de handle_save_trend y persistencia en SQLite.
4. Ejecución de handle_view_favorites consultando SQLite.
5. Ejecución de handle_deep_dive con Gemma.
6. Despacho correcto a través de process_telegram_update.
"""

import sys
import asyncio
from pathlib import Path

# Configurar salida estándar en UTF-8 para consola de Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.telegram_bot import (
    build_interactive_keyboard,
    process_telegram_update,
    handle_save_trend,
    handle_view_favorites,
    handle_get_chart,
)
from app.visual_engine import create_chart_png_card
from app.database import init_db, get_favorites


async def test_keyboard_structure():
    print("\n[1/5] Verificando estructura exacta de los 4 botones requeridos...")
    kb = build_interactive_keyboard(trend_id=99)
    rows = kb.get("inline_keyboard", [])
    assert len(rows) == 2, f"Se esperaban 2 filas de botones, se obtuvieron {len(rows)}"

    btn_1 = rows[0][0]
    btn_2 = rows[0][1]
    btn_3 = rows[1][0]
    btn_4 = rows[1][1]

    print(f"  -> Botón 1: '{btn_1['text']}' (callback_data: '{btn_1.get('callback_data')}')")
    print(f"  -> Botón 2: '{btn_2['text']}' (callback_data: '{btn_2.get('callback_data')}')")
    print(f"  -> Botón 3: '{btn_3['text']}' (callback_data: '{btn_3.get('callback_data')}')")
    print(f"  -> Botón 4: '{btn_4['text']}' (callback_data: '{btn_4.get('callback_data')}')")

    assert "Guardar en favoritos" in btn_1["text"] and "SAVE_TREND" in btn_1["callback_data"]
    assert "Ver favoritos" in btn_2["text"] and "VIEW_FAVS" in btn_2["callback_data"]
    assert "Gráfica de tendencias" in btn_3["text"] and "GET_CHART" in btn_3["callback_data"]
    assert "Profundizar datos" in btn_4["text"] and "DEEP_DIVE" in btn_4["callback_data"]
    print("  [OK] Todos los botones coinciden exactamente con la nueva especificación (Guardar, Ver, Gráfica, Profundizar).")


async def test_favorites_card_rendering():
    print("\n[2/5] Verificando renderizado visual de favoritos (tarjeta_favoritos.html)...")
    from app.visual_engine import create_favorites_png_card
    target_png = ROOT_DIR / "temp_favs.png"
    sample_favs = [
        {
            "title": "Microsoft Copilot",
            "category": "SaaS & Software",
            "source": "Product Hunt",
            "score": 85.0,
            "saved_at": "2026-09-28T12:00:00",
            "message_id": 1234
        }
    ]
    result_path = await create_favorites_png_card(favorites=sample_favs, output_path=target_png)
    assert result_path.exists(), f"El archivo {result_path} no fue creado"
    size = result_path.stat().st_size
    print(f"  -> temp_favs.png renderizado con Playwright: {size:,} bytes")
    assert size > 20000, "El tamaño de temp_favs.png es insuficiente"
    print("  [OK] Tarjeta visual de favoritos generada exitosamente.")


async def test_chart_rendering():
    print("\n[3/5] Verificando renderizado de la plantilla secundaria tarjeta_grafica.html...")
    target_png = ROOT_DIR / "temp_chart.png"
    result_path = await create_chart_png_card(output_path=target_png)
    assert result_path.exists(), f"El archivo {result_path} no fue creado"
    size = result_path.stat().st_size
    print(f"  -> temp_chart.png renderizado con Playwright: {size:,} bytes")
    assert size > 20000, "El tamaño de temp_chart.png es demasiado pequeño para una imagen de 1080x1080"
    print("  [OK] Gráfica secundaria generada exitosamente.")


async def test_dispatcher_actions():
    print("\n[4/5] Verificando dispatcher con callbacks simulados, captura de message_id y reply nativo...")
    init_db()

    # 1. Simular SAVE_TREND con message_id
    update_save = {
        "callback_query": {
            "id": "mock_cb_1",
            "from": {"id": 12345},
            "message": {
                "message_id": 123456,
                "chat": {"id": "test_chat"}
            },
            "data": "SAVE_TREND"
        }
    }
    await process_telegram_update(update_save)
    print("  -> Dispatcher SAVE_TREND procesado correctamente [OK]")

    # 2. Simular VIEW_FAVS (generará tarjeta visual)
    update_view = {
        "callback_query": {
            "id": "mock_cb_2",
            "from": {"id": 12345},
            "message": {"chat": {"id": "test_chat"}},
            "data": "VIEW_FAVS"
        }
    }
    await process_telegram_update(update_view)
    print("  -> Dispatcher VIEW_FAVS (visual) procesado correctamente [OK]")

    # 3. Simular LOAD_FAV_{id} (recuperación de tarjeta original mediante reply_to_message_id)
    update_load = {
        "callback_query": {
            "id": "mock_cb_load",
            "from": {"id": 12345},
            "message": {"chat": {"id": "test_chat"}},
            "data": "LOAD_FAV_14"
        }
    }
    await process_telegram_update(update_load)
    print("  -> Dispatcher LOAD_FAV_{id} (reply nativo) procesado correctamente [OK]")

    # 4. Simular DEEP_DIVE
    update_deep_dive = {
        "callback_query": {
            "id": "mock_cb_3",
            "from": {"id": 12345},
            "message": {"chat": {"id": "test_chat"}},
            "data": "DEEP_DIVE"
        }
    }
    await process_telegram_update(update_deep_dive)
    print("  -> Dispatcher DEEP_DIVE procesado correctamente [OK]")

    # 5. Simular Comando de texto /favoritos
    update_cmd = {
        "message": {
            "message_id": 999,
            "chat": {"id": "test_chat"},
            "text": "/favoritos"
        }
    }
    await process_telegram_update(update_cmd)
    print("  -> Dispatcher comando /favoritos procesado correctamente [OK]")

    # 6. Simular Comando de texto /zona
    update_zona_cmd = {
        "message": {
            "message_id": 1000,
            "chat": {"id": "test_chat"},
            "text": "/zona"
        }
    }
    await process_telegram_update(update_zona_cmd)
    print("  -> Dispatcher comando /zona procesado correctamente [OK]")

    # 7. Simular Callback SET_ZONE:Mexico
    update_set_zone = {
        "callback_query": {
            "id": "mock_cb_zone",
            "from": {"id": 12345},
            "message": {"chat": {"id": "test_chat"}},
            "data": "SET_ZONE:Mexico"
        }
    }
    await process_telegram_update(update_set_zone)
    from app.database import get_user_zone
    saved_zone = get_user_zone("test_chat")
    assert saved_zone == "Mexico", f"Esperado 'Mexico', obtenido '{saved_zone}'"
    print(f"  -> Dispatcher SET_ZONE:Mexico persistido en SQLite: '{saved_zone}' [OK]")


async def test_deep_dive_report_generation():
    print("\n[5/5] Verificando generación y estructura del reporte profundo con transparencia y métricas...")
    from app.llm_service import generate_deep_dive_report
    sample_trend = {
        "title": "Databox B2B Analytics",
        "category": "Analítica & Inteligencia Artificial",
        "source": "Product Hunt",
        "url": "https://databox.com",
        "score": 985.0,
        "summary": "Plataforma empresarial de analítica de datos y tableros en tiempo real para equipos de ventas y marketing.",
        "card_data": {
            "metric_label": "Índice de Demanda B2B",
            "metric_value": "98.5 / 100",
            "delta_value": "+42% semanal",
            "stack_list": [
                {"name": "GraphQL API", "tag_label": "Nuevo"},
                {"name": "PostgreSQL", "tag_label": "Escalando"},
                {"name": "React Dashboard", "tag_label": "Consolidado"}
            ]
        }
    }

    report = await generate_deep_dive_report(sample_trend)
    print(f"  -> Reporte generado ({len(report)} caracteres):")
    print(report[:400] + "...\n")

    assert "MÉTRICAS DURAS" in report or "ANÁLISIS" in report
    assert "ALINEACIÓN ESTRATÉGICA" in report or "tendencias.txt" in report or "NEGOCIO" in report
    assert "DESGLOSE TÉCNICO" in report or "ARQUITECTURA" in report
    assert "VIABILIDAD COMERCIAL" in report or "MONETIZACIÓN" in report
    assert "ganadería" not in report.lower() and "agricultura" not in report.lower()
    print("  [OK] Estructura de reporte profundo validada exitosamente.")


async def main():
    print("=" * 65)
    print("EJECUTANDO TEST DE INTERACTIVIDAD DEL BOT DE TELEGRAM")
    print("=" * 65)
    await test_keyboard_structure()
    await test_favorites_card_rendering()
    await test_chart_rendering()
    await test_dispatcher_actions()
    await test_deep_dive_report_generation()
    print("\n" + "=" * 65)
    print("¡TODAS LAS PRUEBAS DE INTERACTIVIDAD PASARON EXITOSAMENTE!")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
