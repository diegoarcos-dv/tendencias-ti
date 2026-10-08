"""Proveedor de Datos: Agenda Tech & Calendario de Eventos TI en CDMX (Especial Jóvenes y Estudiantes).

Responsabilidades:
- Catálogo interactivo tipo calendario con múltiples eventos tecnológicos en Ciudad de México.
- Enfoque especial en jóvenes desarrolladores, estudiantes, comunidades de código abierto, hackathones y meetups libres.
- Calcula dinámicamente fechas relativas y reales del calendario actual.
- Provee datos formateados para tarjetas individuales por evento y para el carrusel de navegación.
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
        "registration_url": "https://lu.ma/cdmx"
    },
    {
        "id": "evento_python_jovenes",
        "org": "Python CDMX & Comunidades Libres",
        "access_label": "Entrada Libre",
        "title": "Taller Práctico: Crea tu Primer Copiloto con Python & FastAPI",
        "days_ahead": 5,
        "hour_str": "18:30 hrs",
        "venue": "The Pool Coworking, Goldsmith 40, Polanco, CDMX",
        "target_audience": "Jóvenes aprendiendo backend, Python y APIs",
        "requirements": (
            "• Confirmación de asistencia en la página del meetup (sin costo).<br>"
            "• Nivel principiante a intermedio en programación.<br>"
            "• Sesión de networking, mentorías 1 a 1 y pizza al terminar."
        ),
        "tags": [
            "Para Principiantes",
            "Python 3.12",
            "Mentoría Tech",
            "Networking Joven"
        ],
        "registration_url": "https://www.meetup.com/python-cdmx"
    },
    {
        "id": "evento_gdg_estudiantes",
        "org": "Google Developer Student Clubs & GDG CDMX",
        "access_label": "Cupo Libre Estudiantes",
        "title": "Cloud, Contenedores & Web Móvil para Nuevas Generaciones",
        "days_ahead": 8,
        "hour_str": "17:00 hrs",
        "venue": "WeWork Reforma 26, Juárez, Cuauhtémoc, CDMX",
        "target_audience": "Estudiantes de ingeniería, bootcamps y autodidactas",
        "requirements": (
            "• Registro en la plataforma oficial de Google Developers.<br>"
            "• Identificación oficial en torniquetes del edificio.<br>"
            "• Swag oficial (stickers, playeras) para los primeros 50 asistentes."
        ),
        "tags": [
            "Google Developers",
            "Docker / Cloud",
            "Comunidad Estudiantil",
            "Presencial CDMX"
        ],
        "registration_url": "https://gdg.community.dev"
    },
    {
        "id": "evento_nvidia_ia",
        "org": "NVIDIA Developer Community",
        "access_label": "Sujeto a Confirmación",
        "title": "AI Agents Architecture & GPU Compute Night",
        "days_ahead": 12,
        "hour_str": "18:30 hrs",
        "venue": "Torre Virreyes, Pedregal 24, Molino del Rey, CDMX",
        "target_audience": "Desarrolladores apasionados por GPUs y modelos de lenguaje",
        "requirements": (
            "• Identificación oficial obligatoria en recepción.<br>"
            "• Registro previo con correo institucional o personal.<br>"
            "• Demostraciones interactivas de inferencia local con hardware acelerado."
        ),
        "tags": [
            "Agentes con LLM",
            "Inferencia con GPUs",
            "Big Tech",
            "Torre Virreyes"
        ],
        "registration_url": "https://lu.ma/cdmx"
    },
    {
        "id": "evento_aws_community",
        "org": "AWS Community Day México",
        "access_label": "Registro Abierto",
        "title": "Cloud Native, Serverless & Oportunidades Junior en Cloud",
        "days_ahead": 15,
        "hour_str": "09:00 hrs",
        "venue": "WTC Ciudad de México, Montecito 38, Nápoles, CDMX",
        "target_audience": "Jóvenes buscando certificaciones y su primer empleo en la nube",
        "requirements": (
            "• Registro previo en la web oficial de AWS.<br>"
            "• Acceso a área de sponsors con ofertas para talento junior/trainee.<br>"
            "• Talleres prácticos guiados por arquitectos de soluciones certificados."
        ),
        "tags": [
            "AWS Certificaciones",
            "Primer Empleo TI",
            "Conferencia WTC",
            "Networking Masivo"
        ],
        "registration_url": "https://aws.amazon.com/events"
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
        "registration_url": feat.get("registration_url", "https://lu.ma/cdmx"),
        "current_index": idx,
        "total_items": total
    }


def get_latest_events_cdmx(ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna el primer evento del calendario."""
    return get_events_cdmx_by_index(0, ref_date=ref_date)
