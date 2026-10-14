"""Módulo lector de la Fuente de Verdad del Negocio (tendencias.txt).

Responsabilidades:
- Leer e ingerir en memoria el archivo local de tendencias.
- Evitar alucinaciones en el pipeline de IA proveyendo el contexto de negocio estricto.
- Proveer métodos de búsqueda, categorización y coincidencia de palabras clave.
"""

import os
from pathlib import Path
from typing import Optional, List, Dict, Set
import logging
from app.config import settings

logger = logging.getLogger(__name__)


class BusinessContextReader:
    """Gestiona la lectura y consulta en memoria del archivo de tendencias del negocio."""

    def __init__(self, context_file_path: Optional[Path] = None):
        self.context_file_path = context_file_path or settings.BUSINESS_CONTEXT_FILE
        self._raw_content: str = ""
        self._categories: Dict[str, List[str]] = {}
        self._keywords: Set[str] = set()
        self.load_context()

    def load_context(self) -> str:
        """Carga o recarga el archivo de contexto a memoria."""
        path = self.context_file_path
        if not path.is_file():
            # Intentar fallback a rutas relativas alternativas comunes
            fallbacks = [
                settings.BASE_DIR / "data" / "tendencias.txt",
                settings.BASE_DIR / "data" / "tendencias.md",
                settings.BASE_DIR / "tendencias.txt",
            ]
            for fb in fallbacks:
                if fb.is_file():
                    path = fb
                    break

        if not path.is_file():
            logger.warning(
                f"Archivo de contexto no encontrado en: {self.context_file_path}. Se iniciará con contexto vacío."
            )
            self._raw_content = ""
            return ""

        try:
            with open(path, "r", encoding="utf-8") as f:
                self._raw_content = f.read()

            self._parse_sections()
            logger.info(
                f"Contexto de negocio cargado exitosamente desde '{path}' ({len(self._raw_content)} caracteres)."
            )
        except Exception as e:
            logger.error(f"Error al leer el archivo de contexto '{path}': {e}")
            self._raw_content = ""

        return self._raw_content

    def _parse_sections(self) -> None:
        """Parsea encabezados de secciones y palabras clave básicas para evaluación rápida."""
        self._categories.clear()
        self._keywords.clear()

        current_category = "General"
        for line in self._raw_content.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            if line_str.startswith("#"):
                current_category = line_str.lstrip("#").strip()
                if current_category not in self._categories:
                    self._categories[current_category] = []
            elif line_str.startswith("-") or line_str.startswith("*"):
                bullet = line_str.lstrip("-* ").strip()
                self._categories.setdefault(current_category, []).append(bullet)
                # Extraer palabras clave de más de 4 letras
                words = [
                    w.lower().strip(".,;:()[]{}\"'")
                    for w in bullet.split()
                    if len(w) > 4
                ]
                self._keywords.update(words)

    @property
    def raw_content(self) -> str:
        """Retorna el contenido de texto íntegro en memoria."""
        if not self._raw_content:
            self.load_context()
        return self._raw_content

    @property
    def categories(self) -> Dict[str, List[str]]:
        """Retorna las secciones y directrices catalogadas."""
        return self._categories

    @property
    def keywords(self) -> Set[str]:
        """Conjunto de palabras clave de negocio identificadas."""
        return self._keywords

    def is_relevant_to_business(self, title: str, summary: str = "") -> bool:
        """Comprueba de forma heurística y rigurosa si un elemento tiene afinidad con TI, software y negocios B2B."""
        import re
        raw_text = f"{title} {summary}"
        text_lower = raw_text.lower()

        # 1. Filtro Perimetral Anti-Nota Roja, Deportes, Farándula y Contenido General No-Tecnológico
        exclusion_terms = (
            # Crimen y nota roja
            "capturan", "detienen", "detenido", "detenida", "arrestan", "arresto", "cjng",
            "cártel", "cartel", "sicarios", "balacera", "homicidio", "asesinato", "ejecutado",
            "ejecutan", "fosa", "narcotráfico", "narco", "comandante", "fiscalía", "fgr",
            "policía", "policia", "gn", "marina", "sedena", "secuestro", "crimen",
            "delincuencia", "violencia", "robo", "asalto", "presunto líder", "líder criminal",
            # Deportes y eventos masivos
            "futbol", "fútbol", "partido", "champions", "liga mx", "gol", "goles",
            "liverpool", "madrid", "barcelona", "américa", "chivas", "cruz azul",
            "estadio", "delantero", "director técnico", "jornada 1", "jornada 2",
            # Farándula, espectáculos y virales
            "falleció", "fallece", "muere", "muerto", "muerta", "luto", "concierto",
            "boletos", "cantante", "actriz", "actor", "boda", "divorcio", "horóscopo",
            "horoscopo", "lotería", "loteria", "sorteo", "día de muertos", "dia de muertos"
        )
        if any(term in text_lower for term in exclusion_terms):
            return False

        # 2. Términos compuestos tecnológicos de alta especificidad
        compound_terms = (
            "e-commerce", "comercio electrónico", "comercio electronico",
            "inteligencia artificial", "software empresarial", "business intelligence",
            "analítica web", "analitica web", "microservicios", "cloud computing",
            "desarrollo de software", "machine learning", "deep learning",
            "agente de ia", "agentes de ia", "ai agent", "ai agents",
            "ciberseguridad", "seguridad informática", "seguridad informatica",
            "open source", "código abierto", "codigo abierto", "base de datos",
            "automatización de procesos", "automatizacion de procesos",
            "pipeline ci/cd", "ci/cd", "devops", "fintech", "saas b2b"
        )
        if any(term in text_lower for term in compound_terms):
            return True

        # 3. Acrónimos técnicos exactos en mayúsculas (evita falsos positivos con pronombres como 'ti' o 'ia')
        raw_upper_tokens = set(re.findall(r"\b[A-Z]{2,4}\b", raw_text))
        strict_acronyms = {"TI", "IA", "AI", "API", "APIS", "ERP", "CRM", "RPA", "SaaS", "B2B", "LLM", "LLMS", "SDK", "AWS", "GCP"}
        if raw_upper_tokens.intersection(strict_acronyms):
            return True

        # 4. Palabras clave técnicas estrictas (mínimo 3 caracteres, sin pronombres ambiguos)
        tokens = set(re.findall(r"\b[a-zA-ZáéíóúÁÉÍÓÚñÑ0-9_-]+\b", text_lower))
        strict_keywords = {
            "ecommerce", "saas", "b2b", "software", "analytics", "analitica", "analítica",
            "iot", "api", "apis", "copilot", "automatizacion", "automatización",
            "rpa", "llm", "llms", "erp", "crm", "devops", "cloud", "ciberseguridad",
            "fintech", "healthtech", "martech", "adtech", "proptech", "edtech",
            "kubernetes", "docker", "python", "typescript", "microservices",
            "algoritmo", "algoritmos", "código", "codigo", "frontend", "backend",
            "fullstack", "servidor", "database", "postgres", "mongodb"
        }
        if tokens.intersection(strict_keywords):
            return True

        # 5. Intersección con palabras clave del contexto institucional (tendencias.txt)
        intersect = tokens.intersection(self._keywords)
        return len(intersect) >= 2


# Instancia singleton para ser reutilizada en toda la aplicación
business_context = BusinessContextReader()
