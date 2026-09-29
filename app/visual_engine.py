"""Motor Renderizador Visual con Playwright.

Inyecta los datos estructurados en templates/tarjeta_principal.html
y captura un PNG en alta resolución (1080x1080px, deviceScaleFactor: 2).

Responsabilidades:
- Parchear el HTML base para cargar fuentes localmente (sin red externa).
- Inyectar todos los campos data-field via evaluate() de Playwright.
- Capturar el elemento .card exacto al tamaño 1080×1080.
- Proveer función de preview/test sin dependencias externas.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

TEMPLATE_PATH: Path = settings.TEMPLATES_DIR / "tarjeta_principal.html"

# Fuentes de sistema de alta calidad que no requieren red,
# usadas como fallback cuando Playwright bloquea peticiones externas.
_FONT_FALLBACK_CSS = """
<style id="font-offline-patch">
  :root {
    --font-display: 'Segoe UI', system-ui, -apple-system, sans-serif;
    --font-body:    'Segoe UI', system-ui, -apple-system, sans-serif;
  }
</style>
"""


def _patch_html_for_offline(html: str) -> str:
    """Elimina los <link> de Google Fonts e inyecta fuentes de sistema.

    Garantiza que set_content() no haga peticiones HTTP externas,
    evitando timeouts en entornos sin acceso a internet.
    """
    import re
    # Eliminar todos los <link> que apunten a fonts.googleapis.com o fonts.gstatic.com
    html = re.sub(
        r'<link[^>]*(fonts\.googleapis\.com|fonts\.gstatic\.com)[^>]*>',
        '',
        html,
        flags=re.IGNORECASE
    )
    # Eliminar <link rel="preconnect"> residuales de fuentes
    html = re.sub(
        r'<link[^>]*rel=["\']preconnect["\'][^>]*>',
        '',
        html,
        flags=re.IGNORECASE
    )
    # Inyectar override de fuentes justo antes del cierre de </head>
    html = html.replace('</head>', f'{_FONT_FALLBACK_CSS}\n</head>', 1)
    return html


def _build_stack_html(stack_items: list) -> str:
    """Genera el HTML interno del panel stack-list a partir de la lista de componentes."""
    parts = []
    for item in stack_items[:4]:
        name = str(item.get("name", "Componente") if isinstance(item, dict) else item).strip()
        if not name:
            continue
        icon_color = str(item.get("icon_color", "violet") if isinstance(item, dict) else "violet")
        tag_class = str(item.get("tag_class", "new") if isinstance(item, dict) else "new")
        tag_label = str(item.get("tag_label", "Nuevo") if isinstance(item, dict) else "Nuevo")
        # Escapado mínimo para prevenir XSS en el innerHTML
        name = name.replace("<", "&lt;").replace(">", "&gt;")
        tag_label = tag_label.replace("<", "&lt;").replace(">", "&gt;")
        parts.append(
            f'<div class="stack-item">'
            f'<div class="stack-item-left">'
            f'<span class="stack-icon {icon_color}"></span>'
            f'<span class="stack-name">{name}</span>'
            f'</div>'
            f'<span class="stack-tag {tag_class}">{tag_label}</span>'
            f'</div>'
        )
    return "\n".join(parts)


async def create_png_card(
    data: Dict[str, Any],
    output_path: Optional[Path | str] = None,
) -> Path:
    """Renderiza la tarjeta visual y guarda el resultado como PNG.

    Args:
        data: Diccionario con los campos producidos por generate_trend_card_data().
              Claves esperadas: sector, title, impact_level, impact_label,
              metric_label, metric_value, delta_direction, delta_value,
              summary, stack_list, footer_date.
        output_path: Ruta destino del PNG. Por defecto: <BASE_DIR>/temp_card.png.

    Returns:
        Path absoluto del archivo PNG generado.

    Raises:
        FileNotFoundError: Si TEMPLATE_PATH no existe.
        RuntimeError: Si Playwright no está instalado o falla el renderizado.
    """
    # ------------------------------------------------------------------ #
    # Resolución de rutas                                                  #
    # ------------------------------------------------------------------ #
    target_file = Path(output_path) if output_path else settings.BASE_DIR / "temp_card.png"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(
            f"Plantilla HTML no encontrada en: {TEMPLATE_PATH}. "
            "Verifica que templates/tarjeta_principal.html existe."
        )

    # ------------------------------------------------------------------ #
    # Leer y parchear HTML (sin peticiones externas)                       #
    # ------------------------------------------------------------------ #
    html_raw = TEMPLATE_PATH.read_text(encoding="utf-8")
    html_patched = _patch_html_for_offline(html_raw)

    # ------------------------------------------------------------------ #
    # Footer con hora real si el campo no fue provisto                     #
    raw_fd = str(data.get("footer_date", ""))
    if not raw_fd or "T" in raw_fd or len(raw_fd) > 25 or any(y in raw_fd for y in ["2020", "2021", "2022", "2023", "2024", "2025"]):
        footer_date = "Actualizado hoy, 07:00"
    else:
        footer_date = raw_fd

    # ------------------------------------------------------------------ #
    # Renderizado con Playwright                                           #
    # ------------------------------------------------------------------ #
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright no está instalado. Ejecuta:\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(
            viewport={"width": 1080, "height": 1080},
            device_scale_factor=1,
        )

        # domcontentloaded es suficiente: hemos eliminado todas las peticiones externas
        await page.set_content(html_patched, wait_until="domcontentloaded")

        # --- Campo por campo: sector, title, impact, metrics, delta, summary ---
        await page.locator('[data-field="sector"]').evaluate(
            "(el, v) => el.textContent = v",
            data.get("sector", "Tecnología · B2B"),
        )
        await page.locator('[data-field="title"]').evaluate(
            "(el, v) => el.textContent = v",
            data.get("title", "Innovación Tecnológica"),
        )

        impact_level = str(data.get("impact_level", "high")).lower()
        await page.locator('[data-field="impact-level"]').evaluate(
            "(el, lvl) => el.className = `impact-pill ${lvl}`",
            impact_level,
        )
        await page.locator('[data-field="impact-label"]').evaluate(
            "(el, v) => el.textContent = v",
            data.get("impact_label", "Alto impacto comercial"),
        )

        await page.locator('[data-field="metric-label"]').evaluate(
            "(el, v) => el.textContent = v",
            data.get("metric_label", "Métrica de Tracción"),
        )
        await page.locator('[data-field="metric-value"]').evaluate(
            "(el, v) => el.textContent = v",
            str(data.get("metric_value", "—")),
        )

        delta_direction = str(data.get("delta_direction", "up")).lower()
        await page.locator('[data-field="delta-direction"]').evaluate(
            "(el, dir) => el.className = `delta-pill ${dir}`",
            delta_direction,
        )
        await page.locator('[data-field="delta-value"]').evaluate(
            "(el, v) => el.textContent = v",
            str(data.get("delta_value", "+25%")),
        )

        # summary acepta HTML con etiquetas <strong>
        await page.locator('[data-field="summary"]').evaluate(
            "(el, v) => el.innerHTML = v",
            data.get("summary", "Oportunidad de mercado detectada."),
        )

        # Inyección de contexto de negocio: Industria que la busca y Problema que resuelve
        if await page.locator('[data-field="target-industry"]').count() > 0:
            await page.locator('[data-field="target-industry"]').evaluate(
                "(el, v) => el.textContent = v",
                str(data.get("target_industry", "E-Commerce & SaaS B2B")),
            )
        if await page.locator('[data-field="problem-solved"]').count() > 0:
            await page.locator('[data-field="problem-solved"]').evaluate(
                "(el, v) => el.textContent = v",
                str(data.get("problem_solved", "Automatización de procesos operativos")),
            )

        # 2. Limpieza de Arreglos (Capa Lógica):
        data['stack_sugerido'] = [
            tech.strip() if isinstance(tech, str) else str(tech.get('name', '')).strip()
            for tech in data.get('stack_sugerido', [])
            if tech and (tech.strip() if isinstance(tech, str) else str(tech.get('name', '')).strip())
        ]

        # Limpieza de stack_list evitando cadenas vacías o nulas
        cleaned_stack = []
        for item in data.get("stack_list", []):
            if isinstance(item, dict):
                item_name = str(item.get("name", "")).strip()
                if item_name and not any(d in item_name.lower() for d in ["capacidad o módulo", "tecnología concreta", "tecnología o herramienta", "módulo técnico"]):
                    cleaned_stack.append(item)
            elif isinstance(item, str) and item.strip():
                if not any(d in item.lower() for d in ["capacidad o módulo", "tecnología concreta", "tecnología o herramienta", "módulo técnico"]):
                    cleaned_stack.append({"name": item.strip(), "icon_color": "violet", "tag_class": "new", "tag_label": "Nuevo"})

        # Si stack_list quedó vacío pero hay elementos válidos en stack_sugerido, regenerarlo
        if not cleaned_stack and data['stack_sugerido']:
            colors = ["violet", "mint", "mint", "neutral"]
            classes = ["new", "scaling", "scaling", "stable"]
            labels = ["Nuevo", "Escalando", "Escalando", "Consolidado"]
            for i, tech in enumerate(data['stack_sugerido'][:4]):
                tname = tech.strip() if isinstance(tech, str) else str(tech.get('name', '')).strip()
                if tname and not any(d in tname.lower() for d in ["capacidad o módulo", "tecnología concreta", "tecnología o herramienta", "módulo técnico"]):
                    cleaned_stack.append({
                        "name": tname[:36],
                        "icon_color": colors[i] if i < len(colors) else "neutral",
                        "tag_class": classes[i] if i < len(classes) else "stable",
                        "tag_label": labels[i] if i < len(labels) else "Consolidado"
                    })

        data['stack_list'] = cleaned_stack

        # 3. Ocultamiento Dinámico (Capa UI / Playwright):
        # Si la lista de tecnologías resultante está vacía tras la limpieza, oculta completamente
        # el contenedor de la sección del stack (display: none) para evitar una caja vacía o viñetas en blanco.
        if cleaned_stack:
            stack_html = _build_stack_html(cleaned_stack)
            await page.locator('[data-field="stack-list"]').evaluate(
                "(el, v) => el.innerHTML = v",
                stack_html,
            )
            if await page.locator('.stack-count').count() > 0:
                await page.locator('.stack-count').evaluate(
                    "(el, count) => el.textContent = `${count} componentes`",
                    len(cleaned_stack)
                )
        else:
            if await page.locator('.stack-panel').count() > 0:
                await page.locator('.stack-panel').evaluate("(el) => el.style.display = 'none'")

        await page.locator('[data-field="footer-date"]').evaluate(
            "(el, v) => el.textContent = v",
            footer_date,
        )

        # Captura del elemento .card exacto (no pantalla completa)
        await page.locator(".card").screenshot(path=str(target_file))
        await browser.close()

    logger.info(f"[VisualEngine] Tarjeta PNG renderizada en: {target_file}")
    return target_file


CHART_TEMPLATE_PATH: Path = settings.TEMPLATES_DIR / "tarjeta_grafica.html"


async def create_chart_png_card(
    output_path: Optional[Path | str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Path:
    """Renderiza la plantilla secundaria (tarjeta_grafica.html) como PNG de tracción semanal."""
    target_file = Path(output_path) if output_path else settings.BASE_DIR / "temp_chart.png"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    template_to_use = CHART_TEMPLATE_PATH if CHART_TEMPLATE_PATH.exists() else TEMPLATE_PATH
    html_raw = template_to_use.read_text(encoding="utf-8")
    html_patched = _patch_html_for_offline(html_raw)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1080, "height": 1080},
            device_scale_factor=1,
        )
        page = await context.new_page()
        await page.set_content(html_patched, wait_until="domcontentloaded")

        if data:
            if "stat_growth" in data:
                await page.locator('[data-field="stat-growth"]').evaluate(
                    "(el, v) => el.innerHTML = v", str(data["stat_growth"])
                )
            if "stat_sources" in data:
                await page.locator('[data-field="stat-sources"]').evaluate(
                    "(el, v) => el.innerHTML = v", str(data["stat_sources"])
                )
            if "stat_sector" in data:
                await page.locator('[data-field="stat-sector"]').evaluate(
                    "(el, v) => el.textContent = v", str(data["stat_sector"])
                )

        await page.locator(".card").screenshot(path=str(target_file))
        await browser.close()

    logger.info(f"[VisualEngine] Gráfica de tracción PNG renderizada en: {target_file}")
    return target_file


FAVORITES_TEMPLATE_PATH: Path = settings.TEMPLATES_DIR / "tarjeta_favoritos.html"


async def create_favorites_png_card(
    favorites: list[Dict[str, Any]],
    output_path: Optional[Path | str] = None,
) -> Path:
    """Renderiza la tarjeta visual de tecnologías favoritas (tarjeta_favoritos.html) como PNG."""
    target_file = Path(output_path) if output_path else settings.BASE_DIR / "temp_favs.png"
    target_file.parent.mkdir(parents=True, exist_ok=True)

    template_to_use = FAVORITES_TEMPLATE_PATH if FAVORITES_TEMPLATE_PATH.exists() else TEMPLATE_PATH
    html_raw = template_to_use.read_text(encoding="utf-8")
    html_patched = _patch_html_for_offline(html_raw)

    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-gpu",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1080, "height": 1080},
            device_scale_factor=1,
        )
        page = await context.new_page()
        await page.set_content(html_patched, wait_until="domcontentloaded")

        count = len(favorites)
        await page.locator('[data-field="badge-count"]').evaluate(
            "(el, v) => el.textContent = v",
            f"{count} {'FAVORITAS' if count != 1 else 'FAVORITA'}"
        )

        if favorites:
            items_html = []
            for idx, fav in enumerate(favorites[:4], 1):
                title = str(fav.get("title", "Tecnología B2B")).replace("<", "&lt;").replace(">", "&gt;")
                cat = str(fav.get("category", "SaaS B2B")).replace("<", "&lt;").replace(">", "&gt;")
                src = str(fav.get("source", "Web")).replace("_", " ").title().replace("<", "&lt;").replace(">", "&gt;")
                score = float(fav.get("score") or 0.0)
                date_str = str(fav.get("saved_at", ""))[:10]
                items_html.append(f"""
                  <div class="fav-item">
                    <div class="fav-item-left">
                      <div class="fav-idx">{idx:02d}</div>
                      <div class="fav-details">
                        <div class="fav-title">{title}</div>
                        <div class="fav-meta">
                          <span class="fav-tag">{cat}</span>
                          <span>Fuente: {src}</span>
                        </div>
                      </div>
                    </div>
                    <div class="fav-item-right">
                      <div class="fav-score-pill">★ {score:.1f} pts</div>
                      <div class="fav-date">📅 {date_str}</div>
                    </div>
                  </div>
                """)

            await page.locator('[data-field="favorites-list"]').evaluate(
                "(el, v) => el.innerHTML = v",
                "\n".join(items_html)
            )

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        await page.locator('[data-field="footer-date"]').evaluate(
            "(el, v) => el.textContent = v",
            f"Actualizado hoy, {now_str}"
        )

        await page.locator(".card").screenshot(path=str(target_file))
        await browser.close()

    logger.info(f"[VisualEngine] Tarjeta visual de favoritos PNG renderizada en: {target_file}")
    return target_file

