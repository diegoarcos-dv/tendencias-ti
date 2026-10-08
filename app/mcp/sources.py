"""Fuentes externas de proyectos y contratos freelance de software y tecnología con enfoque en CDMX, Edoméx y México."""

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Any, Optional
import httpx
from app.logger import logger

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Pool curado de convocatorias y contratos B2B para CDMX / Edoméx y Desarrolladores en México
_CDMX_MEXICO_CURATED_PROJECTS: List[Dict[str, Any]] = [
    {
        "id": "cdmx_agente_ia_fintech",
        "title": "Desarrollador de Agentes Autónomos de IA & LLMs",
        "company": "Fintech & Open Finance CDMX",
        "budget": "$3,800 - $5,500 USD / mes (o $70,000 MXN)",
        "url": "https://www.getonbrd.com/jobs/machine-learning-ai",
        "tags": ["Agentes IA", "LangChain", "Python", "FastAPI", "OpenAI APIs", "MCP"],
        "source": "Get on Board (México & LATAM)",
        "location": "Remoto (CDMX / Edoméx - CST)",
        "description": "Diseño e implementación de flujos de agentes con LangChain y APIs de LLMs para automatización transaccional y asistentes conversacionales empresariales."
    },
    {
        "id": "cdmx_backend_python_api",
        "title": "Ingeniero Backend Python & Microservicios Cloud",
        "company": "Consultoría Cloud & Software Polanco",
        "budget": "$3,200 - $4,800 USD / mes (o $60,000 MXN)",
        "url": "https://www.getonbrd.com/jobs/programming",
        "tags": ["Python", "FastAPI", "Docker", "PostgreSQL", "AWS"],
        "source": "Get on Board (México & LATAM)",
        "location": "Remoto / Híbrido CDMX",
        "description": "Desarrollo de APIs RESTful de alta concurrencia, integración de webhooks con pasarelas de pago y despliegue en contenedores Docker sobre AWS."
    },
    {
        "id": "cdmx_fullstack_ai_react",
        "title": "Desarrollador Full Stack (React + Python / IA)",
        "company": "SaaS B2B Santa Fe",
        "budget": "$3,000 - $4,500 USD / mes",
        "url": "https://www.getonbrd.com/jobs/programming",
        "tags": ["React", "TypeScript", "Python", "LLMs", "TailwindCSS"],
        "source": "Get on Board (México & LATAM)",
        "location": "Remoto (Horario Central México)",
        "description": "Construcción de dashboards analíticos e interfaces interactivas conectadas a servicios de inteligencia artificial generativa y pipelines de datos."
    }
]


async def fetch_getonbrd_projects(categories: Optional[List[str]] = None, limit: int = 25) -> List[Dict[str, Any]]:
    """Consulta la API pública de Get on Board, enfocada en oportunidades tech para México y Latinoamérica."""
    cats = categories or ["machine-learning-ai", "programming", "data-science-analytics", "sysadmin-devops-qa"]
    results: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            for cat in cats:
                url = f"https://www.getonbrd.com/api/v0/categories/{cat}/jobs?per_page=12"
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json().get("data", [])
                    for item in data:
                        attrs = item.get("attributes", {})
                        links = item.get("links", {})
                        public_url = links.get("public_url", "")
                        
                        min_sal = attrs.get("min_salary")
                        max_sal = attrs.get("max_salary")
                        if min_sal and max_sal:
                            budget = f"${min_sal:,} - ${max_sal:,} USD / mes"
                        elif min_sal:
                            budget = f"Desde ${min_sal:,} USD / mes"
                        else:
                            budget = "Presupuesto competitivo / Negociable"

                        remote_mod = attrs.get("remote_modality", "remote")
                        countries = attrs.get("countries", [])
                        loc_str = "Remoto (México / LATAM - CST)" if remote_mod in ("remote", "full") else f"Híbrido / Remoto ({', '.join(countries[:2]) if countries else 'México'})"

                        company_info = attrs.get("company", {})
                        comp_name = "Empresa Tecnológica"
                        if isinstance(company_info, dict):
                            comp_name = company_info.get("data", {}).get("attributes", {}).get("name") or "Empresa Tecnológica"

                        desc_text = attrs.get("description_headline") or attrs.get("functions_headline") or ""
                        if not desc_text:
                            raw_desc = attrs.get("description", "")
                            desc_text = re.sub(r"<[^>]+>", "", raw_desc)[:260]

                        tags = attrs.get("tags", [])
                        if not isinstance(tags, list):
                            tags = []
                        tags_clean = [t.get("name") if isinstance(t, dict) else str(t) for t in tags[:5]]
                        
                        results.append({
                            "id": f"getonbrd_{item.get('id')}",
                            "title": attrs.get("title", "Desarrollador de Software"),
                            "company": comp_name,
                            "budget": budget,
                            "url": public_url,
                            "tags": tags_clean,
                            "source": "Get on Board (LATAM & México)",
                            "location": loc_str,
                            "description": desc_text.strip()[:260]
                        })
                        if len(results) >= limit:
                            break
                if len(results) >= limit:
                    break
    except Exception as e:
        logger.warning(f"[MCP Sources] Error consultando Get on Board API: {e}")
    return results


async def fetch_remotive_projects(limit: int = 15) -> List[Dict[str, Any]]:
    """Consulta la API pública de Remotive en busca de trabajos y contratos remotos globales accesibles desde México."""
    url = "https://remotive.com/api/remote-jobs?category=software-dev&limit=30"
    results: List[Dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=_HEADERS) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get("jobs", [])
                for j in jobs[:limit]:
                    loc = j.get("candidate_required_location", "Global / Remoto")
                    salary = j.get("salary") or "Tarifa por acordar / Mercado"
                    results.append({
                        "id": f"remotive_{j.get('id')}",
                        "title": j.get("title", "Software Engineer"),
                        "company": j.get("company_name", "Empresa Remota"),
                        "budget": salary,
                        "url": j.get("url", ""),
                        "tags": j.get("tags", []),
                        "source": "Remotive Remote",
                        "location": f"Remoto ({loc})",
                        "description": re.sub(r"<[^>]+>", "", j.get("description", ""))[:260]
                    })
    except Exception as e:
        logger.warning(f"[MCP Sources] Error consultando Remotive API: {e}")
    return results


async def fetch_reddit_forhire_projects(limit: int = 10) -> List[Dict[str, Any]]:
    """Consulta los feeds públicos de Reddit r/forhire y r/freelance_forhire filtrando publicaciones [Hiring]."""
    subreddits = ["forhire", "freelance_forhire"]
    results: List[Dict[str, Any]] = []

    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/new.json?limit=20"
        try:
            async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "CommercialBot/1.0"}) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    children = data.get("data", {}).get("children", [])
                    for child in children:
                        post = child.get("data", {})
                        title = post.get("title", "")
                        if "[hiring]" in title.lower():
                            clean_title = re.sub(r"\[hiring\]", "", title, flags=re.IGNORECASE).strip()
                            selftext = post.get("selftext", "")
                            
                            budget_match = re.search(r"(\$\s*\d+[\d,]*(?:\s*(?:-\s*\$?\s*\d+[\d,]*))?\s*(?:\/\s*(?:hr|hour|mes|mo|project|fijo))?)", title + " " + selftext, re.IGNORECASE)
                            budget = budget_match.group(1).strip() if budget_match else "Presupuesto a convenir"

                            permalink = post.get("permalink", "")
                            full_url = f"https://reddit.com{permalink}" if permalink else post.get("url", "")

                            results.append({
                                "id": f"reddit_{post.get('id')}",
                                "title": clean_title,
                                "company": f"u/{post.get('author', 'Cliente Reddit')}",
                                "budget": budget,
                                "url": full_url,
                                "tags": [w for w in re.findall(r"\b[A-Za-z#+]{2,}\b", clean_title) if len(w) > 3][:5],
                                "source": f"Reddit r/{sub}",
                                "location": "Remoto Internacional",
                                "description": selftext[:260]
                            })
                            if len(results) >= limit:
                                break
        except Exception as e:
            logger.warning(f"[MCP Sources] Error consultando Reddit r/{sub}: {e}")

    return results


async def fetch_all_freelance_sources() -> List[Dict[str, Any]]:
    """Agrega y unifica ofertas de todas las fuentes, priorizando fuertemente México, CDMX/Edoméx y LATAM."""
    getonbrd = await fetch_getonbrd_projects(limit=20)
    remotive = await fetch_remotive_projects(limit=10)
    reddit = await fetch_reddit_forhire_projects(limit=8)
    # Lista combinada: Curados México + Get on Board (LATAM/México) + Remoto Internacional
    return _CDMX_MEXICO_CURATED_PROJECTS + getonbrd + remotive + reddit
