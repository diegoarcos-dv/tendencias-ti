import os
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

    group_chat_id = os.getenv("TELEGRAM_GROUP_CHAT_ID", "-1004339114906")
    clean_cid = str(group_chat_id).replace("-100", "").lstrip("-")
    group_url = f"https://t.me/c/{clean_cid}"

    if action == "DEMANDA_QUOTE":
        company = get_b2b_demand_by_index(idx)
        text = company.get("financial_quote") or "⚠️ Simulación financiera no disponible."
        evidence_url = company.get("demand_evidence_url")
        evidence_label = company.get("demand_source_label") or "🏛️ Ver Evidencia Pública de Demanda"

        rows = []
        if evidence_url and str(evidence_url).strip().startswith("http"):
            rows.append([{"text": f"{evidence_label} ↗️", "url": str(evidence_url).strip()}])
        rows.extend([
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
                {"text": "🏠 Menú Principal", "callback_data": f"CATALOG_GOTO:{ret_idx}"},
            ],
            [
                {"text": "📁 Mis favoritos", "callback_data": "VIEW_FAVS"},
                {"text": "⚙️ Configuración", "callback_data": "RESET_CONFIG"},
            ],
            [
                {"text": "👥 Ir al Grupo TI", "url": group_url}
            ],
        ])
        kb = {"inline_keyboard": rows}

    elif action == "DEMANDA_SCOPE":
        company = get_b2b_demand_by_index(idx)
        text = company.get("scope_summary") or "⚠️ Ficha técnica no disponible."
        evidence_url = company.get("demand_evidence_url")
        evidence_label = company.get("demand_source_label") or "🏛️ Ver Evidencia Pública de Demanda"

        rows = []
        if evidence_url and str(evidence_url).strip().startswith("http"):
            rows.append([{"text": f"{evidence_label} ↗️", "url": str(evidence_url).strip()}])
        rows.extend([
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
                {"text": "🏠 Menú Principal", "callback_data": f"CATALOG_GOTO:{ret_idx}"},
            ],
            [
                {"text": "📁 Mis favoritos", "callback_data": "VIEW_FAVS"},
                {"text": "⚙️ Configuración", "callback_data": "RESET_CONFIG"},
            ],
            [
                {"text": "👥 Ir al Grupo TI", "url": group_url}
            ],
        ])
        kb = {"inline_keyboard": rows}

    elif action == "GET_STACK":
        from app.telegram_bot import handle_get_stack
        return await handle_get_stack(chat_id=user_id, trend_id=payload.get("trend_id"))

    else:
        logger.warning(f"[process_private_action] acción desconocida: {action}")
        return await send_telegram_message(
            text="❓ Acción no reconocida en el canal privado.",
            chat_id=user_id,
        )

    return await send_telegram_message(
        text=text,
        chat_id=user_id,
        parse_mode="HTML",
        reply_markup=kb,
    )

