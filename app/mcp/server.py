"""Servidor MCP (Model Context Protocol) para Inteligencia de Proyectos Freelance.

Expone herramientas estándar conforme al protocolo MCP para consulta,
calificación y coincidencia semántica de contratos de desarrollo de software.
"""

import time
from typing import List, Dict, Any, Optional
from app.mcp.sources import fetch_all_freelance_sources
from app.logger import logger

# Caché en memoria para evitar saturar las fuentes externas (TTL: 15 minutos)
_CACHE_PROJECTS: List[Dict[str, Any]] = []
_CACHE_TIMESTAMP: float = 0.0
_CACHE_TTL_SECONDS: float = 900.0  # 15 minutos


async def _get_cached_or_fresh_projects() -> List[Dict[str, Any]]:
    global _CACHE_PROJECTS, _CACHE_TIMESTAMP
    now = time.time()
    if _CACHE_PROJECTS and (now - _CACHE_TIMESTAMP < _CACHE_TTL_SECONDS):
        return _CACHE_PROJECTS

    logger.info("[MCP Server] Actualizando repositorio de proyectos freelance desde fuentes remotas...")
    fresh = await fetch_all_freelance_sources()
    if fresh:
        _CACHE_PROJECTS = fresh
        _CACHE_TIMESTAMP = now
    return _CACHE_PROJECTS or fresh


def _score_project_relevance(
    project: Dict[str, Any],
    query_terms: List[str],
    skills: List[str]
) -> float:
    """Calcula un score de relevancia (0 a 100) según la coincidencia de título, tags y descripción."""
    score = 10.0  # Base score para proyectos activos
    title_lower = str(project.get("title", "")).lower()
    desc_lower = str(project.get("description", "")).lower()
    tags_lower = [str(t).lower() for t in project.get("tags", [])]

    # Evaluación de términos clave de búsqueda
    for q in query_terms:
        if not q or len(q) < 2:
            continue
        ql = q.lower()
        if ql in title_lower:
            score += 25.0
        if any(ql in t for t in tags_lower):
            score += 20.0
        if ql in desc_lower:
            score += 10.0

    # Evaluación de habilidades específicas (skills)
    for s in skills:
        if not s or len(s) < 2:
            continue
        sl = s.lower()
        if sl in title_lower:
            score += 30.0
        if any(sl in t for t in tags_lower):
            score += 25.0
        if sl in desc_lower:
            score += 10.0

    return min(score, 100.0)


# ============================================================================
# HERRAMIENTAS MCP ESTÁNDAR
# ============================================================================

async def mcp_tool_search_freelance_projects(
    keywords: Optional[str] = None,
    skills: Optional[List[str]] = None,
    role: Optional[str] = None,
    limit: int = 4
) -> List[Dict[str, Any]]:
    """Herramienta MCP: Busca, filtra y califica proyectos freelance de software y tecnología.
    
    Args:
        keywords: Cadena con términos clave de búsqueda (ej. 'python fastapi backend').
        skills: Lista de tecnologías que domina el usuario (ej. ['Python', 'FastAPI']).
        role: Rol o puesto deseado (ej. 'Backend Developer').
        limit: Cantidad máxima de proyectos a devolver (por defecto 4).
    """
    all_projects = await _get_cached_or_fresh_projects()
    if not all_projects:
        return []

    query_terms: List[str] = []
    if keywords:
        query_terms.extend(keywords.split())
    if role:
        query_terms.extend(role.split())

    clean_skills = [s.strip() for s in (skills or []) if s.strip()]

    scored_projects = []
    for p in all_projects:
        rel_score = _score_project_relevance(p, query_terms=query_terms, skills=clean_skills)
        item = dict(p)
        item["relevance_score"] = round(rel_score, 1)
        scored_projects.append(item)

    # Ordenar por mayor coincidencia
    scored_projects.sort(key=lambda x: x["relevance_score"], reverse=True)

    # Si ningún proyecto superó el umbral básico, devolver los más recientes para que no quede vacío
    filtered = [p for p in scored_projects if p["relevance_score"] >= 20.0]
    final_selection = filtered[:limit] if filtered else scored_projects[:limit]
    return final_selection


async def mcp_tool_get_market_rate_estimate(skill_or_role: str) -> Dict[str, Any]:
    """Herramienta MCP: Retorna la tarifa estimada promedio de mercado para un rol o tecnología en USD/hora."""
    sr = (skill_or_role or "").lower()
    if any(k in sr for k in ("ia", "ai", "machine learning", "llm", "gemma", "langchain")):
        return {"range_hourly_usd": "$55 - $90 USD/hr", "demand_level": "Muy Alta (Crítica)"}
    elif any(k in sr for k in ("python", "fastapi", "django", "backend", "cloud", "aws", "docker")):
        return {"range_hourly_usd": "$40 - $65 USD/hr", "demand_level": "Alta"}
    elif any(k in sr for k in ("unity", "unreal", "game", "videojuegos", "c#", "c++")):
        return {"range_hourly_usd": "$45 - $70 USD/hr", "demand_level": "Alta"}
    elif any(k in sr for k in ("react", "frontend", "vue", "nextjs", "javascript")):
        return {"range_hourly_usd": "$35 - $55 USD/hr", "demand_level": "Media-Alta"}
    elif any(k in sr for k in ("ui", "ux", "diseño", "design", "figma")):
        return {"range_hourly_usd": "$30 - $50 USD/hr", "demand_level": "Media"}
    return {"range_hourly_usd": "$35 - $60 USD/hr", "demand_level": "Estándar"}
