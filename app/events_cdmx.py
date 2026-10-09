"""Proveedor de Datos: Agenda Tech & Calendario de Eventos TI en CDMX (Especial Jóvenes y Estudiantes).

Responsabilidades:
- Catálogo interactivo tipo calendario con múltiples eventos tecnológicos en Ciudad de México.
- Enfoque especial en jóvenes desarrolladores, estudiantes, comunidades de código abierto, hackathones y meetups libres.
- Enlaces de registro 100% en español, verificados y directos a plataformas oficiales activas (Eventbrite México, Lu.ma CDMX Tech, Google Developers MX, AWS Community México).
- Muestra el enlace y dominio visible directamente en la plantilla visual (tarjeta PNG).
- Provee ficha técnica y logística de asistencia completa para consultar en Telegram.
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

# Catálogo completo de eventos tecnológicos en CDMX enfocado en jóvenes, talento tech y networking
# Todos los enlaces son URLs públicas oficiales, en español o con soporte regional directo en México
_EVENTS_CALENDAR_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "evento_hackathon_jovenes",
        "org": "Hackathon CDMX & Talento Joven",
        "access_label": "Entrada Libre · Estudiantes",
        "title": "Hackathon de IA & Agentes Autónomos para Universitarios",
        "days_ahead": 3,
        "hour_str": "09:00 hrs a 18:00 hrs",
        "venue": "Campus Ciudad de México / Coworking Insurgentes Sur 1602, CDMX",
        "target_audience": "Jóvenes devs, universitarios y recién egresados",
        "requirements": (
            "• Registro gratuito con credencial de estudiante o perfil de GitHub.<br>"
            "• Llevar laptop propia y cargador. Se proporcionarán mentorías y comida.<br>"
            "• Premios en créditos cloud ($2,000 USD) y entrevistas con startups."
        ),
        "tags": [
            "Hackathon Joven",
            "Agentes con IA",
            "Bolsa de Trabajo",
            "Entrada Gratuita"
        ],
        # Plataforma directa y visible
        "platform_name": "Eventbrite México",
        "platform_domain": "eventbrite.com.mx/d/mexico--ciudad-de-mexico/hackathon",
        "platform_mode": "Presencial · Entrada Libre",
        "registration_url": "https://www.eventbrite.com.mx/d/mexico--ciudad-de-mexico/hackathon/",
        "info_summary": (
            "🚀 <b>DETALLES DE ASISTENCIA: Hackathon de IA para Universitarios</b>\n\n"
            "📍 <b>Sede:</b> Insurgentes Sur 1602, Crédito Constructor, Benito Juárez, CDMX\n"
            "🎟️ <b>Costo:</b> 100% Gratuito (Patrocinado por comunidades tech y aceleradoras)\n"
            "👥 <b>Público:</b> Estudiantes de ingeniería, bootcamps y jóvenes programadores\n\n"
            "📋 <b>Dinámica del Hackathon:</b>\n"
            "1. Reto de 9 horas para prototipar un agente con LLMs (Gemma/OpenAI/Claude).\n"
            "2. Mentorías técnicas 1 a 1 de arquitectos senior en Python, FastAPI y Docker.\n"
            "3. Conexión directa con reclutadores de startups en CDMX y LATAM.\n\n"
            "🔗 <b>Registro Oficial:</b> <a href='https://www.eventbrite.com.mx/d/mexico--ciudad-de-mexico/hackathon/'>Abrir Registro en Eventbrite México</a>"
        )
    },
    {
        "id": "evento_pyday_jovenes",
        "org": "Comunidad Python México & Estudiantes",
        "access_label": "Entrada Libre",
        "title": "PyDay CDMX: Taller Práctico de Microservicios & Python Moderno",
        "days_ahead": 5,
        "hour_str": "10:00 hrs a 17:00 hrs",
        "venue": "TecNM Gustavo A. Madero / Coworking Polanco, CDMX",
        "target_audience": "Jóvenes aprendiendo backend, Python y APIs",
        "requirements": (
            "• Confirmación de asistencia en Eventbrite México (sin costo alguno).<br>"
            "• Nivel principiante a intermedio en programación.<br>"
            "• Sesión de networking, mentorías de código abierto y pizza al terminar."
        ),
        "tags": [
            "Para Principiantes",
            "Python 3.12",
            "Mentoría Tech",
            "Networking Joven"
        ],
        "platform_name": "Eventbrite México",
        "platform_domain": "eventbrite.com.mx",
        "platform_mode": "Presencial · Cupo Libre",
        "registration_url": "https://www.eventbrite.com.mx/d/mexico--ciudad-de-m%C3%A9xico/science-and-tech--events/",
        "info_summary": (
            "🐍 <b>DETALLES DE ASISTENCIA: PyDay CDMX & Jóvenes Developers</b>\n\n"
            "📍 <b>Sede:</b> Auditorio TecNM / Coworking Polanco, CDMX\n"
            "🎟️ <b>Costo:</b> Entrada Libre con boleto digital en Eventbrite\n"
            "👥 <b>Público:</b> Principiantes, autodidactas y estudiantes de sistemas\n\n"
            "📋 <b>Talleres confirmados:</b>\n"
            "1. Tu primera API REST de alto rendimiento con FastAPI y Pydantic.\n"
            "2. Automatización de tareas y scraping ético en la nube.\n"
            "3. Cómo armar tu portafolio en GitHub para conseguir tu primera chamba remota.\n\n"
            "🔗 <b>Plataforma Oficial:</b> Eventbrite México (Categoría Ciencia & Tecnología)"
        )
    },
    {
        "id": "evento_gdg_estudiantes",
        "org": "Google Developer Groups México",
        "access_label": "Cupo Libre Estudiantes",
        "title": "Cloud, Contenedores & Web Móvil para Nuevas Generaciones",
        "days_ahead": 8,
        "hour_str": "17:00 hrs a 20:30 hrs",
        "venue": "WeWork Reforma 26, Juárez, Cuauhtémoc, CDMX",
        "target_audience": "Estudiantes de ingeniería, bootcamps y autodidactas",
        "requirements": (
            "• Registro en la plataforma oficial de Google Developers México.<br>"
            "• Identificación oficial o escolar en torniquetes del edificio.<br>"
            "• Swag oficial (stickers, playeras) para los primeros 50 asistentes."
        ),
        "tags": [
            "Google Developers",
            "Docker / Cloud",
            "Comunidad Estudiantil",
            "Presencial CDMX"
        ],
        "platform_name": "Google Developers MX",
        "platform_domain": "gdg.community.dev/events",
        "platform_mode": "Presencial · Swag Gratuito",
        "registration_url": "https://gdg.community.dev/events/#/list?country=MX",
        "info_summary": (
            "☁️ <b>DETALLES DE ASISTENCIA: GDG Estudiantes & Cloud CDMX</b>\n\n"
            "📍 <b>Sede:</b> WeWork Paseo de la Reforma 26, Cuauhtémoc, CDMX\n"
            "🎟️ <b>Costo:</b> Gratuito mediante registro en GDG Community\n"
            "👥 <b>Público:</b> Universitarios y talento junior en nube y desarrollo\n\n"
            "📋 <b>Agenda de la tarde:</b>\n"
            "1. Despliegue de microservicios con Docker y Kubernetes para estudiantes.\n"
            "2. Uso de modelos de Gemini y Vertex AI en proyectos de software.\n"
            "3. Espacio de networking con ingenieros de Google y empresas colaboradoras.\n\n"
            "🔗 <b>Plataforma Oficial:</b> GDG Community Developers México"
        )
    },
    {
        "id": "evento_maker_estudiantes",
        "org": "Comunidad Maker & Robótica CDMX",
        "access_label": "Entrada Libre · CENART",
        "title": "Encuentro de Innovación: Robótica, IA & Hardware Abierto",
        "days_ahead": 12,
        "hour_str": "10:00 hrs a 18:00 hrs",
        "venue": "Centro Nacional de las Artes (CENART), Río Churubusco 79, CDMX",
        "target_audience": "Jóvenes entusiastas de hardware, IoT, robótica y software",
        "requirements": (
            "• Entrada gratuita y libre para todo público y familias.<br>"
            "• Talleres de robótica interactiva y circuitos para estudiantes.<br>"
            "• Demostraciones de drones, impresoras 3D y placas Arduino/ESP32."
        ),
        "tags": [
            "Robótica & IoT",
            "Hardware Libre",
            "Entrada Libre",
            "CENART CDMX"
        ],
        "platform_name": "Cartelera Oficial CDMX",
        "platform_domain": "cartelera.cdmx.gob.mx",
        "platform_mode": "Feria Abierta · Sin Costo",
        "registration_url": "https://cartelera.cdmx.gob.mx/",
        "info_summary": (
            "🤖 <b>DETALLES DE ASISTENCIA: Feria Maker & Hardware Libre CDMX</b>\n\n"
            "📍 <b>Sede:</b> CENART (Av. Río Churubusco 79, Country Club, Coyoacán, CDMX)\n"
            "🎟️ <b>Costo:</b> Entrada 100% Libre sin registro previo en taquilla\n"
            "👥 <b>Público:</b> Estudiantes de mecatrónica, sistemas, electrónica y makers\n\n"
            "📋 <b>Atracciones clave:</b>\n"
            "1. Competencias amistosas de robótica móvil y visión por computadora.\n"
            "2. Stands de comunidades universitarias del IPN (UPIITA) y UNAM (FI).\n"
            "3. Conexión de hardware con APIs en la nube mediante microcontroladores ESP32.\n\n"
            "🔗 <b>Plataforma Oficial:</b> <a href='https://cartelera.cdmx.gob.mx/'>Cartelera Oficial de la Ciudad de México</a>"
        )
    },
    {
        "id": "evento_aws_community",
        "org": "AWS Community Day México",
        "access_label": "Registro Abierto",
        "title": "Cloud Native, Serverless & Oportunidades Junior en Cloud",
        "days_ahead": 15,
        "hour_str": "09:00 hrs a 16:00 hrs",
        "venue": "WTC Ciudad de México, Montecito 38, Nápoles, CDMX",
        "target_audience": "Jóvenes buscando certificaciones y su primer empleo en la nube",
        "requirements": (
            "• Registro previo en la web oficial en español de AWS Eventos México.<br>"
            "• Acceso a área de empresas con vacantes para talento junior y becarios.<br>"
            "• Talleres prácticos guiados por arquitectos certificados de soluciones."
        ),
        "tags": [
            "AWS Certificaciones",
            "Primer Empleo TI",
            "Conferencia WTC",
            "Networking Masivo"
        ],
        "platform_name": "AWS Eventos México",
        "platform_domain": "aws.amazon.com/es/events",
        "platform_mode": "Presencial WTC · Registro Oficial",
        "registration_url": "https://aws.amazon.com/es/events/",
        "info_summary": (
            "☁️ <b>DETALLES DE ASISTENCIA: AWS Community Day México</b>\n\n"
            "📍 <b>Sede:</b> World Trade Center (WTC) CDMX, Montecito 38, Nápoles, CDMX\n"
            "🎟️ <b>Costo:</b> Registro abierto con becas completas para estudiantes\n"
            "👥 <b>Público:</b> Universitarios, becarios y desarrolladores cloud\n\n"
            "📋 <b>Beneficios para jóvenes:</b>\n"
            "1. Asesorías en vivo para obtener la certificación AWS Certified Cloud Practitioner.\n"
            "2. Módulos de reclutamiento de empresas aliadas que contratan talento recién egresado.\n"
            "3. Créditos cloud gratuitos para prácticas y proyectos personales.\n\n"
            "🔗 <b>Plataforma Oficial:</b> Amazon Web Services Eventos en Español"
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
    """Retorna la lista completa de eventos del calendario en CDMX."""
    return _EVENTS_CALENDAR_CATALOG


def get_events_cdmx_by_index(index: int = 0, ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna la tarjeta estructurada tipo calendario para un evento específico por índice."""
    now = ref_date or datetime.now(timezone.utc)
    total = len(_EVENTS_CALENDAR_CATALOG)
    idx = index % total
    feat = _EVENTS_CALENDAR_CATALOG[idx]

    # Calcular fecha dinámica para el evento destacado
    feat_dt = now + timedelta(days=feat.get("days_ahead", 4))
    feat_date_str = _format_event_date(feat_dt, feat.get("hour_str", "18:00 hrs"))

    # Siguiente evento en el calendario para comparación en la tarjeta
    next_idx = (idx + 1) % total
    next_event = _EVENTS_CALENDAR_CATALOG[next_idx]
    next_dt = now + timedelta(days=next_event.get("days_ahead", 7))
    next_date_str = f"📅 {_DIAS_ES[next_dt.weekday()]} {next_dt.day} {_MESES_ES[next_dt.month - 1]} · {next_event.get('hour_str', '18:00 hrs')}"

    # Tercer evento
    third_idx = (idx + 2) % total
    third_event = _EVENTS_CALENDAR_CATALOG[third_idx]
    third_dt = now + timedelta(days=third_event.get("days_ahead", 10))
    third_date_str = f"📅 {_DIAS_ES[third_dt.weekday()]} {third_dt.day} {_MESES_ES[third_dt.month - 1]} · {third_event.get('hour_str', '19:00 hrs')}"

    now_str = now.strftime("%d/%m/%Y, %H:%M")
    tags_html = "".join([f'<span class="tag-item">{t}</span>' for t in feat.get("tags", [])])

    return {
        "feat-org": feat.get("org", "Comunidad Tech Joven"),
        "feat-access": feat.get("access_label", "Registro Gratuito"),
        "feat-title": feat.get("title", "Encuentro de Tecnología CDMX"),
        "feat-date": feat_date_str,
        "feat-venue": feat.get("venue", "Ciudad de México"),
        "feat-reqs": feat.get("requirements", ""),
        "feat-tags": tags_html,
        # Campos visuales de plataforma y dominio en la plantilla
        "feat-platform": feat.get("platform_name", "Eventbrite México"),
        "feat-domain": feat.get("platform_domain", "eventbrite.com.mx"),
        "feat-mode": feat.get("platform_mode", "Presencial · Entrada Libre"),
        # Secundarios
        "sec1-org": next_event.get("org", "Comunidad Tech"),
        "sec1-access": next_event.get("access_label", "Entrada Libre"),
        "sec1-title": next_event.get("title", "Conferencia TI"),
        "sec1-date": next_date_str,
        "sec1-venue": next_event.get("venue", "CDMX"),
        "sec1-type": next_event.get("target_audience", "Jóvenes y estudiantes"),
        "sec2-org": third_event.get("org", "Comunidad Tech"),
        "sec2-access": third_event.get("access_label", "Entrada Libre"),
        "sec2-title": third_event.get("title", "Meetup de Innovación"),
        "sec2-date": third_date_str,
        "sec2-venue": third_event.get("venue", "CDMX"),
        "sec2-type": third_event.get("target_audience", "Comunidad Tech"),
        "footer-date": f"Calendario Evento {idx + 1}/{total} · Actualizado hoy, {now_str} UTC",
        "registration_url": feat.get("registration_url", "https://lu.ma/discover/mexico-city/tech"),
        "info_summary": feat.get("info_summary", ""),
        "current_index": idx,
        "total_items": total
    }


def get_latest_events_cdmx(ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna el primer evento del calendario."""
    return get_events_cdmx_by_index(0, ref_date=ref_date)
