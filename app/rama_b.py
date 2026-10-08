import logging
from typing import Dict, Any

from app.telegram_bot import send_telegram_message
from app.b2b_demand import get_b2b_demand_by_index

logger = logging.getLogger(__name__)


async def process_private_action(user_id: str, payload: Dict[str, Any]) -> None:
    """
    Despacha la acción solicitada hacia la conversación privada (DM) con el usuario.

    payload = {
        "action": "DEMANDA_QUOTE" | "DEMANDA_SCOPE" | "GET_STACK",
        "idx": <int>,            # índice de la empresa demandante
        "return_idx": <int>,     # índice de retorno
    }
    """
    action = payload.get("action")
    idx = int(payload.get("idx", 0))
    ret_idx = int(payload.get("return_idx", 0))

    if action == "DEMANDA_QUOTE":
        company = get_b2b_demand_by_index(idx)
        text = company.get("financial_quote") or "⚠️ Simulación financiera no disponible."
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "🏢 Perfil Oficial en LinkedIn",
                        "url": company.get("linkedin_company_url")
                        or company.get("linkedin_search_url")
                        or "https://www.linkedin.com",
                    }
                ],
                [
                    {
                        "text": "📋 Ver Alcance & SOW",
                        "callback_data": f"DEMANDA_SCOPE:{idx}:{ret_idx}",
                    }
                ],
                [
                    {
                        "text": "🔙 Volver a la Empresa",
                        "callback_data": f"NAV_DEMANDA_PAGE:curr:{idx}:{ret_idx}",
                    },
                    {"text": "🏠 Inicio", "callback_data": f"CATALOG_GOTO:{ret_idx}"},
                ],
            ]
        }

    elif action == "DEMANDA_SCOPE":
        company = get_b2b_demand_by_index(idx)
        text = company.get("scope_summary") or "⚠️ Ficha técnica no disponible."
        kb = {
            "inline_keyboard": [
                [
                    {
                        "text": "📊 Simular Cotización & Margen",
                        "callback_data": f"DEMANDA_QUOTE:{idx}:{ret_idx}",
                    }
                ],
                [
                    {
                        "text": "🏢 Perfil Oficial en LinkedIn",
                        "url": company.get("linkedin_company_url")
                        or company.get("linkedin_search_url")
                        or "https://www.linkedin.com",
                    }
                ],
                [
                    {
                        "text": "🔙 Volver a la Empresa",
                        "callback_data": f"NAV_DEMANDA_PAGE:curr:{idx}:{ret_idx}",
                    },
                    {"text": "🏠 Inicio", "callback_data": f"CATALOG_GOTO:{ret_idx}"},
                ],
            ]
        }

    elif action == "GET_STACK":
        from app.telegram_bot import handle_get_stack
        await handle_get_stack(chat_id=user_id, trend_id=payload.get("trend_id"))
        return

    else:
        logger.warning(f"[process_private_action] acción desconocida: {action}")
        await send_telegram_message(
            text="❓ Acción no reconocida en el canal privado.",
            chat_id=user_id,
        )
        return

    await send_telegram_message(
        text=text,
        chat_id=user_id,
        parse_mode="HTML",
        reply_markup=kb,
    )
