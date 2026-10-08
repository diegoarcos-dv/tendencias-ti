"""Cliente MCP: Conecta el bot de Telegram con el servidor MCP de Oportunidades Freelance."""

from typing import List, Dict, Any, Optional
from app.database import get_user_freelance_profile
from app.mcp.server import mcp_tool_search_freelance_projects, mcp_tool_get_market_rate_estimate
from app.logger import logger


async def get_freelance_opportunities_for_user(
    chat_id: str,
    trend_stack: Optional[str] = None,
    limit: int = 4
) -> Dict[str, Any]:
    """Obtiene las mejores oportunidades freelance emparejadas con el perfil del usuario o la tendencia.
    
    Retorna un diccionario con:
    - 'user_profile': Datos del perfil freelance del usuario
    - 'projects': Lista de proyectos calificados por el servidor MCP
    - 'formatted_text': Texto HTML listo para enviar en Telegram con botones y enlaces
    """
    user_prof = get_user_freelance_profile(chat_id)
    role = user_prof.get("role", "")
    skills = user_prof.get("skills", [])
    keywords = user_prof.get("keywords", "")

    # Si se pasa un stack específico de una tarjeta de tendencia, se enriquece la búsqueda
    combined_keywords = f"{keywords} {trend_stack or ''}".strip()
    if trend_stack and isinstance(skills, list):
        combined_skills = list(set(skills + [s.strip() for s in trend_stack.replace(",", " ").split() if len(s.strip()) > 2]))
    else:
        combined_skills = skills

    projects = await mcp_tool_search_freelance_projects(
        keywords=combined_keywords,
        skills=combined_skills,
        role=role,
        limit=limit
    )

    market_rate = await mcp_tool_get_market_rate_estimate(role or trend_stack or "Software Developer")

    return {
        "user_profile": user_prof,
        "market_rate": market_rate,
        "projects": projects
    }


def format_freelance_projects_html(
    opportunities: Dict[str, Any],
    trend_title: Optional[str] = None
) -> str:
    """Genera el mensaje formateado en HTML con guardrails de escape para Telegram."""
    prof = opportunities.get("user_profile", {})
    rate = opportunities.get("market_rate", {})
    projects = opportunities.get("projects", [])

    role = prof.get("role") or "Desarrollador de Software"
    skills_str = ", ".join(prof.get("skills", [])) or "Tecnología & Código"
    rate_str = rate.get("range_hourly_usd", "$35 - $60 USD/hr")

    lines = [
        "💼 <b>Radar de Oportunidades Freelance & Contratos Remotos</b>",
        "<i>Consultado en tiempo real vía Servidor MCP (Remotive / Reddit / WeWorkRemotely)</i>\n",
        f"🎯 <b>Perfil:</b> {role}",
        f"🛠️ <b>Stack:</b> {skills_str}",
        f"💵 <b>Tarifa de Mercado:</b> <code>{rate_str}</code>\n"
    ]

    if trend_title:
        lines.append(f"📌 <i>Filtrado para el ecosistema de: {trend_title}</i>\n")

    if not projects:
        lines.append("⚠️ <i>No se encontraron proyectos activos para este stack en este momento. Intenta actualizar tu perfil profesional o revisar más tarde.</i>")
    else:
        for idx, p in enumerate(projects, 1):
            title = p.get("title", "Proyecto Freelance")
            comp = p.get("company", "Empresa")
            budget = p.get("budget", "Tarifa por acordar")
            src = p.get("source", "Web")
            url = p.get("url", "")
            match = p.get("relevance_score", 0.0)

            lines.append(f"<b>{idx}. 🔹 {title}</b>")
            lines.append(f"   • <b>Cliente / Empresa:</b> {comp} ({src})")
            lines.append(f"   • <b>Presupuesto / Tarifa:</b> <code>{budget}</code>")
            lines.append(f"   • <b>Coincidencia de Stack:</b> {match}%")
            if url:
                lines.append(f"   • 👉 <a href='{url}'>Ver detalles y postularme</a>\n")
            else:
                lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("<i>Utiliza los botones inferiores para navegar sin salir de tu sesión.</i>")

    return "\n".join(lines)
