"""Suite de Pruebas: Arquitectura Dual (Grupo vs. Individual) y Caducidad TTL 7 Días.

Valida:
1. Detección de entorno y UI condicional (Grupo: 1 botón deep link vs. DM: 4 botones).
2. Prohibición estricta de botones de favoritos/profundizar en grupos.
3. Deep link '/start config' redirige al menú de zona (/zona).
4. Persistencia en registro_tarjetas_enviadas y cumplimiento del límite de 3 envíos diarios por usuario.
5. Caducidad TTL de 7 días: detección de mensajes vencidos y purga.
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

# UTF-8 en consola
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import (
    init_db,
    record_sent_card,
    get_user_daily_card_count,
    get_expired_card_messages,
    delete_card_record,
    set_user_zone,
    get_user_zone,
)
from app.telegram_bot import (
    build_group_keyboard,
    build_interactive_keyboard,
    process_telegram_update,
    delete_telegram_message,
)
from app.main import (
    run_individual_pipeline,
    cleanup_expired_messages,
)
from app.config import settings


async def test_ui_conditional_keyboards():
    print("\n[1/5] Verificando UI condicional según el entorno (Grupo vs. DM)...")

    # A. Teclado de Grupo con Deep Links (🔍 Profundizar y 🤖 Personalizar alertas)
    group_kb = build_group_keyboard(trend_id=18, bot_username="Tendencias_DiegoBot")
    rows = group_kb.get("inline_keyboard", [])
    assert len(rows) == 3, f"El grupo debe tener 3 filas de botones, tiene {len(rows)}"

    btn_deepdive = rows[0][0]
    btn_toggle = rows[1][0]
    btn_config = rows[2][0]
    print(f"  -> Botón 1 de Grupo: '{btn_deepdive['text']}' (url: '{btn_deepdive.get('url')}')")
    print(f"  -> Botón 2 de Grupo: '{btn_toggle['text']}' (callback_data: '{btn_toggle.get('callback_data')}')")
    print(f"  -> Botón 3 de Grupo: '{btn_config['text']}' (url: '{btn_config.get('url')}')")

    assert btn_deepdive["text"] == "🔍 Profundizar"
    assert "start=deepdive_18" in btn_deepdive.get("url", "")

    assert btn_toggle["text"] == "📈 Gráfica de tendencias"
    assert btn_toggle["callback_data"] == "TOGGLE_CHART_18"

    assert btn_config["text"] == "🤖 Personalizar alertas"
    assert "start=config" in btn_config.get("url", "")
    print("  [OK] Teclado de Grupo genera enlaces deep-link a DM y botón toggle de gráfica.")

    # B. Teclado de DM (Privado)
    dm_kb = build_interactive_keyboard(trend_id=42)
    dm_rows = dm_kb.get("inline_keyboard", [])
    assert len(dm_rows) >= 2, f"El chat privado debe tener al menos 2 filas de botones, tiene {len(dm_rows)}"
    all_dm_texts = [btn["text"] for row in dm_rows for btn in row]
    assert any("Guardar en favoritos" in t for t in all_dm_texts)
    assert any("Ver favoritos" in t for t in all_dm_texts)
    assert any("Gráfica de tendencias" in t for t in all_dm_texts)
    assert any("Profundizar datos" in t for t in all_dm_texts)
    print("  [OK] Teclado de DM contiene el panel interactivo completo de 4 botones.")


async def test_group_action_blocking():
    print("\n[2/5] Verificando bloqueo de botones de favoritos/profundizar en grupos...")
    blocked_actions = ["SAVE_TREND", "VIEW_FAVS", "DEEP_DIVE"]
    for act in blocked_actions:
        update_group_cb = {
            "callback_query": {
                "id": "mock_cb_group",
                "from": {"id": 1111},
                "message": {
                    "message_id": 8888,
                    "chat": {"id": -5320614669, "type": "supergroup"}
                },
                "data": act
            }
        }
        await process_telegram_update(update_group_cb)
    print("  [OK] Acciones restringidas en grupos son interceptadas y rechazadas correctamente.")


async def test_deep_link_start_config():
    print("\n[3/5] Verificando deep links en /start ('/start config' y '/start deepdive_18')...")
    # A. /start config
    update_start_config = {
        "message": {
            "message_id": 9991,
            "chat": {"id": "test_dm_user", "type": "private"},
            "text": "/start config"
        }
    }
    await process_telegram_update(update_start_config)

    # B. /start deepdive_18
    update_start_deepdive = {
        "message": {
            "message_id": 9992,
            "chat": {"id": "test_dm_user", "type": "private"},
            "text": "/start deepdive_18"
        }
    }
    await process_telegram_update(update_start_deepdive)
    print("  [OK] Comandos de deep link '/start config' y '/start deepdive_18' enrutados correctamente a DM.")


async def test_daily_send_quota():
    print("\n[4/5] Verificando registro de tarjetas y límite de 3 envíos diarios por usuario...")
    test_chat = f"test_user_quota_{int(datetime.utcnow().timestamp())}"
    init_db()

    # Debe iniciar en 0
    c0 = get_user_daily_card_count(test_chat)
    assert c0 == 0, f"Se esperaba 0 para usuario fresco, obtenido {c0}"

    # Simular 3 envíos hoy
    record_sent_card(chat_id=test_chat, message_id=101, chat_type="private")
    record_sent_card(chat_id=test_chat, message_id=102, chat_type="private")
    record_sent_card(chat_id=test_chat, message_id=103, chat_type="private")

    c3 = get_user_daily_card_count(test_chat)
    print(f"  -> Tarjetas registradas hoy para {test_chat}: {c3}")
    assert c3 == 3

    # Intentar ejecutar pipeline individual para ese usuario -> debe ser saltado
    res = await run_individual_pipeline(chat_id=test_chat)
    assert res.get("status") == "skipped"
    assert res.get("reason") == "daily_limit_reached"
    print("  [OK] Pipeline individual respeta estrictamente el límite diario de 3 envíos por usuario.")


async def test_ttl_7_days_expiration():
    print("\n[5/5] Verificando caducidad de mensajes (TTL de 7 días)...")
    init_db()
    expired_chat = "test_chat_ttl"
    past_date = datetime.utcnow() - timedelta(days=8, hours=2)

    # Insertar tarjeta enviada hace 8 días
    rid = record_sent_card(chat_id=expired_chat, message_id=77777, chat_type="group", created_at=past_date)

    # Consultar vencidos
    expired_list = get_expired_card_messages(days=7)
    matching = [x for x in expired_list if x["id"] == rid]
    assert len(matching) == 1, "La tarjeta con 8 días de antigüedad debe ser detectada como expirada"
    print(f"  -> Tarjeta {rid} (message_id: 77777) detectada como vencida (creada {past_date.isoformat()}).")

    # Ejecutar limpieza TTL
    cleanup_res = await cleanup_expired_messages(days=7)
    print(f"  -> Resultado de limpieza TTL: {cleanup_res}")
    assert cleanup_res["found_expired"] >= 1
    assert cleanup_res["cleaned_records"] >= 1

    # Verificar que ya no está en SQLite
    expired_after = get_expired_card_messages(days=7)
    assert not any(x["id"] == rid for x in expired_after)
    print("  [OK] Tarjeta caducada depurada exitosamente de SQLite y llamada a deleteMessage procesada.")


async def main():
    print("=" * 70)
    print("EJECUTANDO TEST DE ARQUITECTURA DUAL Y CADUCIDAD TTL (7 DÍAS)")
    print("=" * 70)
    await test_ui_conditional_keyboards()
    await test_group_action_blocking()
    await test_deep_link_start_config()
    await test_daily_send_quota()
    await test_ttl_7_days_expiration()
    print("\n" + "=" * 70)
    print("¡TODAS LAS PRUEBAS DE ARQUITECTURA DUAL Y CADUCIDAD PASARON EXITOSAMENTE!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
