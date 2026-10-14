import unittest
import re
from typing import Dict, Any
from app.b2b_demand import _SEED_COMPANIES_POOL, get_all_b2b_demand_companies, get_b2b_demand_by_index
from app.telegram_bot import build_demand_keyboard

# TDD: Entities with 100% verified, direct official public software tenders
EXPECTED_ENTITIES = [
    "Fiscalía General de Justicia CDMX",
    "Alcaldía Miguel Hidalgo (CDMX)",
    "Metro CDMX (Sistema de Transporte Colectivo)",
    "Fiscalía General de Justicia CDMX (Cloud)",
    "FGJCDMX & C5 (Ciberseguridad)"
]

OBSOLETE_ENTITIES = [
    "Walmart de México & Centroamérica",
    "Tianguis Digital CDMX (ADIP)",
    "Clip México",
    "Kavak México",
    "Jüsto Supermercado Digital",
    "Clara Gastos Corporativos",
    "Salud Digna & Red de Laboratorios",
    "Openpay by BBVA",
    "Grupo Traxión",
    "Banobras (Banca de Desarrollo)",
    "Infonavit"
]


class TestB2BProcurement(unittest.TestCase):
    def test_seed_pool_entities(self):
        """TDD: Verificar que el catálogo contiene exclusivamente entidades con convocatorias reales de TI."""
        pool_companies = [c["company"] for c in _SEED_COMPANIES_POOL]
        
        # 1. Asegurar que las entidades obsoletas (con páginas de clientes) fueron eliminadas
        for obs in OBSOLETE_ENTITIES:
            self.assertNotIn(obs, pool_companies, f"Error: {obs} no debe estar en el catálogo de licitaciones y compras TI.")
            
        # 2. Asegurar que las entidades esperadas están presentes
        for exp in EXPECTED_ENTITIES:
            self.assertIn(exp, pool_companies, f"Error: {exp} debe estar presente en el catálogo oficial.")

    def test_urls_security_and_https(self):
        """TDD / API-Security: Verificar que todas las URLs de evidencia son HTTPS y sin barreras de login."""
        for c in _SEED_COMPANIES_POOL:
            url = c.get("demand_evidence_url", "")
            self.assertTrue(url.startswith("https://"), f"Seguridad API: {c['company']} debe usar URL HTTPS segura. Obtenida: {url}")
            self.assertNotIn("linkedin.com", url, f"UX/Security: {c['company']} no debe depender de login de LinkedIn.")
            self.assertGreater(len(c.get("demand_source_label", "")), 5, f"UX: {c['company']} debe tener etiqueta descriptiva de fuente.")

    def test_ui_ux_pro_max_keyboard(self):
        """TDD / UI-UX-Pro-Max: Verificar que el teclado tiene exactamente 5 filas, cero redundancia y navegación ergonómica."""
        total = len(_SEED_COMPANIES_POOL)
        for idx in range(total):
            comp = _SEED_COMPANIES_POOL[idx]
            kb = build_demand_keyboard(
                current_index=idx,
                total_items=total,
                return_index=0,
                company_web_url=comp.get("contact_web"),
                demand_evidence_url=comp.get("demand_evidence_url"),
                demand_source_label=comp.get("demand_source_label")
            )
            rows = kb["inline_keyboard"]
            self.assertEqual(len(rows), 5, f"UI-UX Error: El teclado de {comp['company']} debe tener exactamente 5 filas, tiene {len(rows)}")
            
            # Verificar Fila 1 (Navegación)
            self.assertEqual(len(rows[0]), 3)
            self.assertEqual(rows[0][0]["text"], "◀️")
            self.assertEqual(rows[0][2]["text"], "▶️")
            
            # Verificar Fila 2 (Propuesta SOW)
            self.assertIn("Propuesta de Servicio", rows[1][0]["text"])
            
            # Verificar Fila 3 (Cotización)
            self.assertIn("Simular Cotización", rows[2][0]["text"])
            
            # Verificar Fila 4 (Única fuente externa oficial)
            self.assertIn("↗️", rows[3][0]["text"])
            self.assertEqual(rows[3][0]["url"], comp["demand_evidence_url"])
            
            # Verificar Fila 5 (Menú Principal)
            self.assertIn("Menú Principal", rows[4][0]["text"])

    def test_html_safety(self):
        """TDD / Security: Verificar que el contenido HTML de fichas técnicas no contiene etiquetas malformadas ni peligrosas."""
        allowed_tags = {"b", "/b", "code", "/code", "i", "/i", "span", "/span"}
        for c in _SEED_COMPANIES_POOL:
            scope = c.get("scope_summary", "")
            quote = c.get("financial_quote", "")
            for text in [scope, quote]:
                tags = re.findall(r"<([^>]+)>", text)
                for tag in tags:
                    tag_name = tag.split()[0]
                    self.assertIn(tag_name, allowed_tags, f"Seguridad: Etiqueta HTML no permitida '<{tag}>' en {c['company']}")


if __name__ == "__main__":
    unittest.main()

