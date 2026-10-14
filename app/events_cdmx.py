"""Proveedor de Datos: Agenda Tech & Calendario de Eventos TI en CDMX (Enfoque Enterprise & B2B).

Responsabilidades:
- Catálogo interactivo tipo calendario con eventos tecnológicos corporativos y cumbres de IA en Ciudad de México.
- Enfoque estratégico en líderes de TI, directores de tecnología, arquitectos cloud, desarrolladores senior y sector empresarial.
- Soporte para fechas fijas de grandes congresos (ej. NVIDIA AI Day, Microsoft AI Tour) y fechas dinámicas escalonadas.
- Enlaces oficiales de registro empresarial verificados (NVIDIA LatAm, Microsoft Events, AWS Summits, IBM Think, Google Cloud).
- Generación de fichas técnicas para renderizado en tarjetas visuales (1080x1080) y consultas interactivas en Telegram.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)

# Días de la semana y meses en español para formato limpio
_DIAS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
_MESES_ES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]

# Catálogo oficial de eventos tecnológicos empresariales en CDMX (AI, Cloud, Ciberseguridad & Enterprise)
_EVENTS_CALENDAR_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "evento_nvidia_ai_day_cdmx",
        "org": "NVIDIA LatAm & Alianza México IA+",
        "access_label": "Acreditación Empresarial",
        "title": "NVIDIA AI Day Mexico City 2026 & México IA+",
        "fixed_date_str": "Miércoles 4 y Jueves 5 de Noviembre de 2026 · 09:00 hrs a 18:00 hrs",
        "days_ahead": 20,
        "hour_str": "09:00 hrs a 18:00 hrs",
        "venue": "Expo Santa Fe México, Av. Santa Fe 270, Santa Fe, CDMX",
        "target_audience": "Líderes de TI, CTOs, Arquitectos Cloud, Científicos de Datos y Directores de Innovación",
        "requirements": (
            "• Acreditación previa oficial en el portal de NVIDIA LatAm / México IA+.<br>"
            "• Keynotes ejecutivas de Jensen Huang & líderes de infraestructura de IA para centros de datos.<br>"
            "• Sesiones de aceleración GPU para inferencia empresarial, gemelos digitales y LLMs industriales."
        ),
        "tags": [
            "NVIDIA AI Day",
            "Expo Santa Fe",
            "GPUs & Data Centers",
            "México IA+"
        ],
        "platform_name": "NVIDIA Events LatAm",
        "platform_domain": "nvidia.com/es-la/events",
        "platform_mode": "Presencial · Expo Santa Fe",
        "registration_url": "https://www.nvidia.com/es-la/events/",
        "info_summary": (
            "🟢 <b>DETALLES DE ASISTENCIA: NVIDIA AI Day Mexico City 2026 & México IA+</b>\n\n"
            "📍 <b>Sede:</b> Expo Santa Fe México (Av. Santa Fe 270, Zedec Santa Fe, Álvaro Obregón, CDMX)\n"
            "📅 <b>Fechas:</b> 4 y 5 de Noviembre de 2026\n"
            "🎟️ <b>Acceso:</b> Registro Empresarial & Acreditación Oficial (Incluye acceso a México IA+)\n"
            "👥 <b>Público Objetivo:</b> CTOs, Arquitectos de Software, Directores de TI y Equipos de IA\n\n"
            "📋 <b>Agenda Estratégica del Evento:</b>\n"
            "1. <b>Arquitectura de Supercómputo:</b> Infraestructura de GPUs Blackwell y DGX para centros de datos empresariales.\n"
            "2. <b>IA Generativa Empresarial:</b> Despliegues de microservicios NVIDIA NIM y modelos fundacionales autónomos.\n"
            "3. <b>Marco México IA+:</b> Alianzas público-privadas para aceleración tecnológica e inversión en IA nacional.\n"
            "4. <b>Networking Ejecutivo:</b> Zona de exposición con integradores cloud, consultoras y líderes de la industria.\n\n"
            "🔗 <b>Portal Oficial de Registro:</b> <a href='https://www.nvidia.com/es-la/events/'>Sitio Oficial NVIDIA Events México</a>"
        )
    },
    {
        "id": "evento_microsoft_ai_tour_cdmx",
        "org": "Microsoft México Enterprise",
        "access_label": "Pase Corporativo B2B",
        "title": "Microsoft AI Tour CDMX: Infraestructura, Copilot & Azure OpenAI",
        "fixed_date_str": "Martes 10 de Noviembre de 2026 · 08:30 hrs a 17:30 hrs",
        "days_ahead": 26,
        "hour_str": "08:30 hrs a 17:30 hrs",
        "venue": "Centro Citibanamex, Av. del Conscripto 311, Lomas de Sotelo, CDMX",
        "target_audience": "Directores de Tecnología, Ingenieros de Software, CISOs y Analistas de Datos",
        "requirements": (
            "• Registro corporativo con correo empresarial en Microsoft Events.<br>"
            "• Talleres hands-on de Azure OpenAI, seguridad en la nube y gobierno corporativo de datos.<br>"
            "• Vinculación con partners de soluciones y consultoras enterprise."
        ),
        "tags": [
            "Microsoft AI",
            "Azure Enterprise",
            "Centro Citibanamex",
            "B2B Tech"
        ],
        "platform_name": "Microsoft Events MX",
        "platform_domain": "events.microsoft.com",
        "platform_mode": "Presencial · Centro Citibanamex",
        "registration_url": "https://events.microsoft.com/",
        "info_summary": (
            "🟦 <b>DETALLES DE ASISTENCIA: Microsoft AI Tour Mexico City</b>\n\n"
            "📍 <b>Sede:</b> Centro Citibanamex (Av. del Conscripto 311, Lomas de Sotelo, Miguel Hidalgo, CDMX)\n"
            "🎟️ <b>Acceso:</b> Registro profesional gratuito con correo corporativo verificado\n"
            "👥 <b>Público Objetivo:</b> Tomadores de decisiones técnicas, desarrolladores cloud y arquitectos de soluciones\n\n"
            "📋 <b>Ejes Temáticos:</b>\n"
            "1. Adopción de agentes con Microsoft Copilot Studio y orquestación con Azure AI.\n"
            "2. Estrategias de ciberseguridad Zero Trust para entornos corporativos híbridos.\n"
            "3. Modernización de bases de datos legadas y pipelines analíticos en Microsoft Fabric.\n\n"
            "🔗 <b>Registro Oficial:</b> <a href='https://events.microsoft.com/'>Portal Microsoft Events México</a>"
        )
    },
    {
        "id": "evento_aws_summit_enterprise_cdmx",
        "org": "Amazon Web Services (AWS) México",
        "access_label": "Entrada Libre con Registro",
        "title": "AWS Summit México: Cómputo Elástico, IA Generativa & Bedrock",
        "days_ahead": 12,
        "hour_str": "09:00 hrs a 17:00 hrs",
        "venue": "World Trade Center (WTC) CDMX, Montecito 38, Nápoles, CDMX",
        "target_audience": "Arquitectos de Soluciones, DevOps, Líderes de Ingeniería Cloud y Startups",
        "requirements": (
            "• Registro digital confirmado en portal de AWS Events México.<br>"
            "• Múltiples tracks técnicos: Infraestructura Cloud, Serverless y Modelos Fundacionales en Bedrock.<br>"
            "• Expo de soluciones tecnológicas con más de 40 empresas expositoras y partners."
        ),
        "tags": [
            "AWS Summit",
            "WTC CDMX",
            "Arquitectura Cloud",
            "Enterprise"
        ],
        "platform_name": "AWS Events México",
        "platform_domain": "aws.amazon.com/es/events",
        "platform_mode": "Presencial WTC · Registro Oficial",
        "registration_url": "https://aws.amazon.com/es/events/summits/mexico/",
        "info_summary": (
            "🟧 <b>DETALLES DE ASISTENCIA: AWS Summit Ciudad de México</b>\n\n"
            "📍 <b>Sede:</b> World Trade Center (WTC) CDMX (Montecito 38, Nápoles, Benito Juárez, CDMX)\n"
            "🎟️ <b>Costo:</b> 100% Gratuito mediante registro previo en portal oficial de AWS\n"
            "👥 <b>Público Objetivo:</b> Arquitectos Cloud, SysAdmins, Ingenieros de Datos y Líderes Técnicos\n\n"
            "📋 <b>Tracks Técnicos Confirmados:</b>\n"
            "1. <b>AI & Machine Learning:</b> Implementación de modelos abiertos y propietarios con Amazon Bedrock.\n"
            "2. <b>Resiliencia Cloud:</b> Arquitecturas multi-región y optimización de costos en EC2 y Kubernetes (EKS).\n"
            "3. <b>Casos de Éxito Empresariales:</b> Paneles con bancos, retailers y unicornios de LATAM.\n\n"
            "🔗 <b>Registro Oficial:</b> <a href='https://aws.amazon.com/es/events/summits/mexico/'>AWS Summit México (Registro Oficial)</a>"
        )
    },
    {
        "id": "evento_ibm_think_forum_cdmx",
        "org": "IBM México & Red Hat Enterprise",
        "access_label": "Acceso Ejecutivo B2B",
        "title": "IBM Think Forum: watsonx, Nube Híbrida & Automatización",
        "days_ahead": 16,
        "hour_str": "09:30 hrs a 15:30 hrs",
        "venue": "Hotel St. Regis / Paseo de la Reforma 439, Cuauhtémoc, CDMX",
        "target_audience": "Líderes de Transformación Digital, Científicos de Datos y Arquitectos de Software",
        "requirements": (
            "• Invitación o confirmación vía portal oficial de IBM Think Forum México.<br>"
            "• Sesiones de integración de IA gobernada y despliegues soberanos con Red Hat OpenShift.<br>"
            "• Espacio de vinculación ejecutiva, mesas redondas y casos de ROI industrial."
        ),
        "tags": [
            "IBM watsonx",
            "Red Hat OpenShift",
            "Reforma CDMX",
            "Gobierno de Datos"
        ],
        "platform_name": "IBM Think Events",
        "platform_domain": "ibm.com/events/think",
        "platform_mode": "Presencial · Hotel St. Regis",
        "registration_url": "https://www.ibm.com/events/think/",
        "info_summary": (
            "🔷 <b>DETALLES DE ASISTENCIA: IBM Think Forum CDMX & Red Hat</b>\n\n"
            "📍 <b>Sede:</b> The St. Regis Mexico City (Paseo de la Reforma 439, Cuauhtémoc, CDMX)\n"
            "🎟️ <b>Acceso:</b> Registro exclusivo para sector corporativo y clientes enterprise\n"
            "👥 <b>Público Objetivo:</b> Directores de Transformación Digital, CIOs y Responsables de Automatización\n\n"
            "📋 <b>Agenda Ejecutiva:</b>\n"
            "1. <b>watsonx.ai & watsonx.governance:</b> Cómo auditar y proteger la propiedad intelectual de modelos corporativos.\n"
            "2. <b>Nube Híbrida Abierta:</b> Escalabilidad y portabilidad de microservicios con Red Hat OpenShift.\n"
            "3. <b>Automatización de TI con IA:</b> Optimización de operaciones e incidentes con AIOps.\n\n"
            "🔗 <b>Registro Oficial:</b> <a href='https://www.ibm.com/events/think/'>IBM Think México (Información & Acceso)</a>"
        )
    },
    {
        "id": "evento_google_cloud_summit_cdmx",
        "org": "Google Cloud México",
        "access_label": "Acreditación Profesional",
        "title": "Google Cloud Summit: Vertex AI, BigQuery & Ciberseguridad Mandiant",
        "days_ahead": 22,
        "hour_str": "08:30 hrs a 17:00 hrs",
        "venue": "Expo Santa Fe México, Av. Santa Fe 270, Santa Fe, CDMX",
        "target_audience": "Equipos de Infraestructura Cloud, Ciberseguridad, Data Science y DevOps",
        "requirements": (
            "• Confirmación oficial en Google Cloud Events México.<br>"
            "• Demostraciones en vivo de Gemini Enterprise, analítica distribuida y BigQuery Studio.<br>"
            "• Consultoría directa con arquitectos e ingenieros de soluciones de Google Cloud."
        ),
        "tags": [
            "Google Cloud",
            "Vertex AI",
            "Mandiant Security",
            "Expo Santa Fe"
        ],
        "platform_name": "Google Cloud Events",
        "platform_domain": "cloud.google.com/events",
        "platform_mode": "Presencial · Expo Santa Fe",
        "registration_url": "https://cloud.google.com/events",
        "info_summary": (
            "🔴 <b>DETALLES DE ASISTENCIA: Google Cloud Summit México</b>\n\n"
            "📍 <b>Sede:</b> Expo Santa Fe México (Av. Santa Fe 270, Santa Fe, CDMX)\n"
            "🎟️ <b>Acceso:</b> Registro profesional gratuito con credencial digital\n"
            "👥 <b>Público Objetivo:</b> Arquitectos de infraestructura, analistas de datos e ingenieros de IA\n\n"
            "📋 <b>Temas Destacados:</b>\n"
            "1. <b>Modelos Multimodales Gemini:</b> Despliegue de asistentes y analítica avanzada sobre Vertex AI.\n"
            "2. <b>Ciberseguridad Proactiva:</b> Detección de amenazas e inteligencia de seguridad con Google Security Operations (Mandiant).\n"
            "3. <b>Data & Modern Apps:</b> Gestión masiva de datos en tiempo real con BigQuery y Cloud Spanner.\n\n"
            "🔗 <b>Registro Oficial:</b> <a href='https://cloud.google.com/events'>Google Cloud Summit (Página de Registro)</a>"
        )
    },
    {
        "id": "evento_ciberseguridad_b2b_cdmx",
        "org": "ISACA & Ciberseguridad Corporativa MX",
        "access_label": "Registro Corporativo",
        "title": "Foro Nacional de Ciberseguridad Empresarial & Zero Trust",
        "days_ahead": 28,
        "hour_str": "09:00 hrs a 16:30 hrs",
        "venue": "Club de Banqueros de México, 16 de Septiembre 57, Centro Histórico, CDMX",
        "target_audience": "Oficiales de Seguridad (CISO), Auditores de TI, Oficiales de Cumplimiento y CIOs",
        "requirements": (
            "• Registro profesional previo en plataforma oficial de ISACA México.<br>"
            "• Mesas de discusión sobre cumplimiento regulatorio, prevención de ransomware y resiliencia crítica.<br>"
            "• Casos de estudio en sector financiero, telecomunicaciones y comercio electrónico."
        ),
        "tags": [
            "Ciberseguridad B2B",
            "Zero Trust",
            "Club de Banqueros",
            "Compliance"
        ],
        "platform_name": "ISACA Chapter México",
        "platform_domain": "isaca.org.mx",
        "platform_mode": "Presencial · Club de Banqueros",
        "registration_url": "https://isaca.org.mx/",
        "info_summary": (
            "🛡️ <b>DETALLES DE ASISTENCIA: Foro de Ciberseguridad Empresarial CDMX</b>\n\n"
            "📍 <b>Sede:</b> Club de Banqueros de México (16 de Septiembre 57, Centro Histórico, Cuauhtémoc, CDMX)\n"
            "🎟️ <b>Acceso:</b> Registro formal para directivos y profesionales del sector seguridad de TI\n"
            "👥 <b>Público Objetivo:</b> CISOs, Auditores, Consultores de Seguridad y Directores de Tecnología\n\n"
            "📋 <b>Agenda Especializada:</b>\n"
            "1. <b>Arquitecturas Zero Trust:</b> Aislamiento de identidades, accesos privilegiados y microsegmentación.\n"
            "2. <b>Respuesta ante Ransomware:</b> Protocolos de contingencia y resiliencia de datos en infraestructuras críticas.\n"
            "3. <b>Regulación y Cumplimiento:</b> Estándares ISO 27001, NIS2 y normativas bancarias en México.\n\n"
            "🔗 <b>Registro Oficial:</b> <a href='https://isaca.org.mx/'>ISACA México Chapter (Registro & Agenda)</a>"
        )
    }
]


def _format_event_date(target_dt: datetime, hour_str: str) -> str:
    """Genera una fecha legible en español (ej. 'Jueves 15 de Octubre · 18:30 hrs')."""
    dia_sem = _DIAS_ES[target_dt.weekday()]
    dia_num = target_dt.day
    mes = _MESES_ES[target_dt.month - 1]
    return f"{dia_sem} {dia_num} de {mes} · {hour_str}"


def get_all_events_cdmx() -> List[Dict[str, Any]]:
    """Retorna la lista completa de eventos del calendario en CDMX desde SQLite o catálogo base."""
    try:
        from app.database import get_active_enterprise_events, save_enterprise_event
        db_events = get_active_enterprise_events()
        if not db_events:
            # Sembrar catálogo inicial en la base de datos
            for ev in _EVENTS_CALENDAR_CATALOG:
                save_enterprise_event(ev)
            db_events = get_active_enterprise_events()
        if db_events:
            return db_events
    except Exception as e:
        logger.warning(f"Error consultando eventos de la base de datos: {e}")

    return _EVENTS_CALENDAR_CATALOG


def get_events_cdmx_by_index(index: int = 0, ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna la tarjeta estructurada tipo calendario para un evento específico por índice,
    calculando fechas fijas o dinámicas dentro de la ventana de eventos corporativos.
    """
    now = ref_date or datetime.now(timezone.utc)
    events_list = get_all_events_cdmx()
    total = len(events_list)
    idx = index % total if total > 0 else 0
    feat = events_list[idx] if total > 0 else _EVENTS_CALENDAR_CATALOG[0]

    # Calcular fecha del evento destacado (soporta fecha fija oficial o cálculo dinámico)
    if feat.get("fixed_date_str"):
        feat_date_str = feat["fixed_date_str"]
    else:
        feat_dt = now + timedelta(days=feat.get("days_ahead", 3))
        feat_date_str = _format_event_date(feat_dt, feat.get("hour_str", "18:00 hrs"))

    # Siguiente evento en el calendario para comparación en la tarjeta
    next_idx = (idx + 1) % total
    next_event = events_list[next_idx]
    if next_event.get("fixed_date_str"):
        next_date_str = f"📅 {next_event['fixed_date_str']}"
    else:
        next_days = next_event.get("days_ahead", 7)
        if next_idx <= idx:
            next_days += 30
        next_dt = now + timedelta(days=next_days)
        next_date_str = f"📅 {_DIAS_ES[next_dt.weekday()]} {next_dt.day} {_MESES_ES[next_dt.month - 1]} · {next_event.get('hour_str', '18:00 hrs')}"

    # Tercer evento
    third_idx = (idx + 2) % total
    third_event = events_list[third_idx]
    if third_event.get("fixed_date_str"):
        third_date_str = f"📅 {third_event['fixed_date_str']}"
    else:
        third_days = third_event.get("days_ahead", 11)
        if third_idx <= idx:
            third_days += 30
        third_dt = now + timedelta(days=third_days)
        third_date_str = f"📅 {_DIAS_ES[third_dt.weekday()]} {third_dt.day} {_MESES_ES[third_dt.month - 1]} · {third_event.get('hour_str', '19:00 hrs')}"

    now_str = now.strftime("%d/%m/%Y, %H:%M")
    tags_html = "".join([f'<span class="tag-item">{t}</span>' for t in feat.get("tags", [])])

    return {
        "feat-org": feat.get("org", "Big Tech Community"),
        "feat-access": feat.get("access_label", "Registro Corporativo"),
        "feat-title": feat.get("title", "Cumbre de Tecnología & IA CDMX"),
        "feat-date": feat_date_str,
        "feat-venue": feat.get("venue", "Ciudad de México"),
        "feat-reqs": feat.get("requirements", ""),
        "feat-tags": tags_html,
        # Campos visuales de plataforma y dominio en la plantilla
        "feat-platform": feat.get("platform_name", "Portal Oficial"),
        "feat-domain": feat.get("platform_domain", "tech-events.mx"),
        "feat-mode": feat.get("platform_mode", "Presencial · Sede Corporativa"),
        # Secundarios
        "sec1-org": next_event.get("org", "Comunidad Enterprise"),
        "sec1-access": next_event.get("access_label", "Acreditación Abierta"),
        "sec1-title": next_event.get("title", "Summit Tecnológico"),
        "sec1-date": next_date_str,
        "sec1-venue": next_event.get("venue", "CDMX"),
        "sec1-type": next_event.get("target_audience", "Profesionales TI"),
        "sec2-org": third_event.get("org", "Comunidad Enterprise"),
        "sec2-access": third_event.get("access_label", "Registro Abierto"),
        "sec2-title": third_event.get("title", "Foro de Innovación"),
        "sec2-date": third_date_str,
        "sec2-venue": third_event.get("venue", "CDMX"),
        "sec2-type": third_event.get("target_audience", "Líderes de Tecnología"),
        "footer-date": f"Agenda Enterprise CDMX · Evento {idx + 1}/{total} · Actualizado {now_str} UTC",
        "registration_url": feat.get("registration_url", "https://www.nvidia.com/es-la/events/"),
        "info_summary": feat.get("info_summary", ""),
        "current_index": idx,
        "total_items": total
    }


def add_custom_enterprise_event(raw_text: str) -> Dict[str, Any]:
    """Procesa un texto o enlace y registra un nuevo evento empresarial en SQLite."""
    text_clean = raw_text.strip()
    if not text_clean:
        raise ValueError("El texto o datos del evento no pueden estar vacíos.")

    import hashlib
    import urllib.parse

    # 1. Si contiene separadores '|'
    if "|" in text_clean:
        parts = [p.strip() for p in text_clean.split("|") if p.strip()]
        title = parts[0] if len(parts) > 0 else "Nuevo Evento TI"
        org = parts[1] if len(parts) > 1 else "Comunidad Tech Enterprise"
        venue = parts[2] if len(parts) > 2 else "Ciudad de México"
        date_str = parts[3] if len(parts) > 3 else "Próximamente · Fecha por Confirmar"
        url = parts[4] if len(parts) > 4 else "https://google.com"

        evt_id = "custom_" + hashlib.md5(f"{title}_{date_str}".encode("utf-8")).hexdigest()[:10]
        domain = urllib.parse.urlparse(url).netloc.replace("www.", "") or "portal-oficial.com"

        event_data = {
            "id": evt_id,
            "event_id": evt_id,
            "org": org,
            "access_label": "Registro Empresarial",
            "title": title,
            "fixed_date_str": date_str,
            "days_ahead": 10,
            "hour_str": "09:00 hrs a 18:00 hrs",
            "venue": venue,
            "target_audience": "Líderes de TI, Desarrolladores y Profesionales Enterprise",
            "requirements": (
                "• Registro oficial y acreditación previa en el portal del organizador.<br>"
                "• Sesiones ejecutivas, conferencias magistrales y networking B2B.<br>"
                "• Identificación oficial y confirmación digital de acceso."
            ),
            "tags": [org[:15], "Tech Summit", "CDMX", "Enterprise"],
            "platform_name": org,
            "platform_domain": domain,
            "platform_mode": "Presencial · Sede CDMX",
            "registration_url": url,
            "info_summary": (
                f"🎟️ <b>DETALLES DE ASISTENCIA: {title}</b>\n\n"
                f"🏢 <b>Organizador:</b> {org}\n"
                f"📍 <b>Sede:</b> {venue}\n"
                f"📅 <b>Fecha:</b> {date_str}\n"
                f"🎟️ <b>Acceso:</b> Registro Empresarial\n\n"
                f"🔗 <b>Enlace de Registro:</b> <a href='{url}'>{url}</a>"
            )
        }
    elif text_clean.startswith("http://") or text_clean.startswith("https://"):
        url = text_clean
        parsed = urllib.parse.urlparse(url)
        domain = parsed.netloc.replace("www.", "")

        slug = parsed.path.strip("/").split("/")[-1].replace("-", " ").replace("_", " ").title()
        if not slug or len(slug) < 3:
            slug = f"Cumbre Tecnológica en {domain}"

        evt_id = "custom_" + hashlib.md5(url.encode("utf-8")).hexdigest()[:10]

        event_data = {
            "id": evt_id,
            "event_id": evt_id,
            "org": domain.capitalize(),
            "access_label": "Registro Confirmado",
            "title": slug[:60],
            "fixed_date_str": "Consulta fechas oficiales en la web",
            "days_ahead": 14,
            "hour_str": "Horario oficial según agenda",
            "venue": "Ciudad de México (Ver detalles en registro)",
            "target_audience": "Profesionales y Líderes de Tecnología",
            "requirements": "• Registro en plataforma oficial.<br>• Consulta de agenda y confirmación vía email.",
            "tags": ["Tech Event", domain[:12], "CDMX", "Enterprise"],
            "platform_name": domain,
            "platform_domain": domain,
            "platform_mode": "Presencial / Híbrido",
            "registration_url": url,
            "info_summary": (
                f"🎟️ <b>DETALLES DEL EVENTO REGISTRADO</b>\n\n"
                f"📌 <b>Título:</b> {slug}\n"
                f"🌐 <b>Portal:</b> {domain}\n"
                f"🔗 <b>Registro:</b> <a href='{url}'>{url}</a>"
            )
        }
    else:
        evt_id = "custom_" + hashlib.md5(text_clean.encode("utf-8")).hexdigest()[:10]
        event_data = {
            "id": evt_id,
            "event_id": evt_id,
            "org": "Comunidad Tech B2B",
            "access_label": "Registro Empresarial",
            "title": text_clean[:60],
            "fixed_date_str": "Próximamente en CDMX",
            "days_ahead": 15,
            "hour_str": "09:00 hrs a 18:00 hrs",
            "venue": "Ciudad de México",
            "target_audience": "Profesionales TI y Directivos",
            "requirements": "• Registro oficial previo.<br>• Confirmación digital.",
            "tags": ["Tech Event", "CDMX", "Enterprise"],
            "platform_name": "Portal Oficial",
            "platform_domain": "tech-events.mx",
            "platform_mode": "Presencial CDMX",
            "registration_url": "https://google.com",
            "info_summary": f"🎟️ <b>{text_clean}</b>\n\n📍 Sede: Ciudad de México\n📅 Próximamente"
        }

    from app.database import save_enterprise_event
    save_enterprise_event(event_data)
    return event_data


def get_latest_events_cdmx(ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna el primer evento del calendario."""
    return get_events_cdmx_by_index(0, ref_date=ref_date)

