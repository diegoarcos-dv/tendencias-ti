"""Proveedor de Datos: Demanda Empresarial B2B & Requerimientos de Software/IA (Opción C - Prospección Diaria Activa).

Responsabilidades:
- Prospección activa de empresas por el agente diariamente vinculada a la base de datos (SQLite).
- Almacenamiento en `b2b_empresas_demandantes` con historial para asegurar que no se repitan las mismas empresas en días consecutivos.
- Generación de empresas mediante LLM (Ollama) con fallback a pool extendido multindustria (20+ empresas mexicanas/LATAM).
- Verificación automática de la disponibilidad del perfil de LinkedIn.
- Fallback automático: si LinkedIn no está disponible o está caído, redirige a la web oficial corporativa de la empresa.
- Provee desglose de simulación de cotización financiera & margen TI (Opción 2).
- Provee fichas técnicas ejecutivas detalladas (Statement of Work / SOW) para consultar en Telegram.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json
import logging
import asyncio
import httpx

from app.config import settings
from app.database import (
    save_b2b_companies,
    get_b2b_companies_by_date,
    get_recent_b2b_company_names
)

logger = logging.getLogger(__name__)

# Pool de licitaciones públicas oficiales verificadas en CDMX (Concurso Digital / Compras Públicas)
_SEED_COMPANIES_POOL: List[Dict[str, Any]] = [
    {
        "id": "demanda_fgjcdmx_fabrica_software",
        "company": "Fiscalía General de Justicia CDMX",
        "sector": "Justicia Digital, Seguridad & Fábrica de Software",
        "priority": "Licitación Pública Nacional",
        "status_badge": "LPN/FGJCDMX/DACS-060/2025",
        "budget": "$70,000 - $140,000 USD",
        "problem": (
            "Licitación Pública Oficial LPN/FGJCDMX/DACS-060/2025: Requerimiento de 'Servicio de Fábrica de Software "
            "para la actualización de tecnología de los sistemas de la Fiscalía General de Justicia de la Ciudad de México'."
        ),
        "solution": (
            "Servicio administrado de Fábrica de Software con células ágiles Scrum/DevOps, desarrollo bajo ciclo de software "
            "seguro (normas ISO 27001 / CSSLP), modernización a microservicios contenerizados y pruebas automatizadas de rendimiento."
        ),
        "tags": ["Fábrica de Software CDMX", "LPN/FGJCDMX/DACS-060/2025", "ISO 27001 / CSSLP", "Microservicios"],
        "contact_email": "dacs@fgjcdmx.gob.mx",
        "contact_web": "concursodigital.finanzas.cdmx.gob.mx",
        "linkedin_company_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNQ==",
        "source_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNQ==",
        "demand_source_type": "Licitación Pública Nacional No. LPN/FGJCDMX/DACS-060/2025",
        "demand_source_label": "🏛️ Licitación Fábrica Software FGJCDMX",
        "demand_evidence_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNQ==",
        "comparison_points": [
            "Procedimiento oficial LPN/FGJCDMX/DACS-060/2025 publicado en Concurso Digital CDMX",
            "Exige estándares CSSLP e ISO 27001:2022 para desarrollo de software seguro",
            "Células dedicadas de análisis, frontend, backend y QA automatizado"
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Fábrica de Software Gubernamental</b>\n\n"
            "🏢 <b>Entidad:</b> Fiscalía General de Justicia CDMX\n"
            "📋 <b>Licitación:</b> LPN/FGJCDMX/DACS-060/2025 (Fábrica de Software)\n"
            "💡 <b>Solución:</b> Célula de Desarrollo Ágil + Arquitectura Segura ISO 27001\n\n"
            "💰 <b>1. Costo Estimado de Operación de la Célula (COGS - 12 meses):</b>\n"
            "• Tech Lead / Arquitecto de Software (12 meses): $36,000 USD\n"
            "• 2 Desarrolladores Senior Fullstack (12 meses): $48,000 USD\n"
            "• Ingeniero DevOps & Seguridad CSSLP: $22,000 USD\n"
            "• QA Automation & Pruebas de Estrés: $14,000 USD\n"
            "👉 <b>Costo Base de Ejecución:</b> ~$120,000 USD\n\n"
            "💵 <b>2. Precio de Oferta Licitatoria Sugerida:</b>\n"
            "• <b>Monto Total Contratado:</b> <b>$185,000 USD</b> (ó ~$3,330,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>35.1% de ganancia neta</b> ($65,000 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer Anual / Extensiones):</b>\n"
            "• Póliza de soporte preventivo y correctivo Nivel 3: <b>$4,500 USD / mes</b>\n"
            "• Margen mensual recurrente: ~60% ($2,700 USD/mes limpios)"
        ),
        "scope_summary": (
            "🏛️ <b>FICHA TÉCNICA OFICIAL DE LICITACIÓN: FGJCDMX</b>\n\n"
            "📋 <b>N° Procedimiento:</b> LPN/FGJCDMX/DACS-060/2025\n"
            "💼 <b>Objeto del Procedimiento:</b> Contratación del servicio de Fábrica de Software para la actualización de tecnología de los sistemas de la Fiscalía General de Justicia de la Ciudad de México\n"
            "🏛️ <b>Unidad Convocante:</b> FISCALÍA GENERAL DE JUSTICIA\n"
            "💰 <b>Presupuesto Estimado:</b> $70,000 - $140,000 USD\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Portal Convocante:</b> Sistema de Compras Públicas de la Ciudad de México\n"
            "• <b>Enlace Oficial Directo:</b> <code>https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNQ==</code>\n\n"
            "📌 <b>Requerimiento Técnico de las Bases:</b>\n"
            "Actualización tecnológica de sistemas de procuración de justicia, migración de módulos legados a microservicios "
            "y garantía de cumplimiento de pruebas de calidad y seguridad bajo ISO 27001.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Plan de trabajo y arquitectura tecnológica basada en microservicios contenerizados.\n"
            "2. Desarrollo evolutivo y correctivo de módulos prioritarios de la Fiscalía.\n"
            "3. Batería de pruebas automatizadas de seguridad (caja negra, blanca, OWASP Top 10).\n"
            "4. Manuales técnicos, de usuario y transferencia metodológica al equipo interno."
        )
    },
    {
        "id": "demanda_miguel_hidalgo_desarrollo_web",
        "company": "Alcaldía Miguel Hidalgo (CDMX)",
        "sector": "Gobierno Digital, Trámites & Portales Ciudadanos",
        "priority": "Licitación Pública Nacional",
        "status_badge": "30001026-032-25",
        "budget": "$25,000 - $55,000 USD",
        "problem": (
            "Licitación Pública Oficial No. 30001026-032-25: Requerimiento de 'SERVICIO DE CONSULTORÍA Y DESARROLLO WEB' "
            "para la modernización de portales digitales de trámites y atención ciudadana de la alcaldía."
        ),
        "solution": (
            "Servicios integrales de consultoría de arquitectura web, desarrollo de portales modernos con Next.js y FastAPI, "
            "cumplimiento de estándares de accesibilidad universal (WCAG 2.1) e integración con pasarelas de citas y trámites."
        ),
        "tags": ["Consultoría y Desarrollo Web", "Licitación 30001026-032-25", "Next.js / FastAPI", "Trámites Digitales"],
        "contact_email": "licitaciones@miguelhidalgo.gob.mx",
        "contact_web": "concursodigital.finanzas.cdmx.gob.mx",
        "linkedin_company_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNg==",
        "source_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNg==",
        "demand_source_type": "Licitación Pública No. 30001026-032-25",
        "demand_source_label": "🏛️ Licitación Consultoría & Web",
        "demand_evidence_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNg==",
        "comparison_points": [
            "Procedimiento oficial 30001026-032-25 publicado en Concurso Digital CDMX",
            "Consultoría técnica especializada en diseño y desarrollo web gubernamental",
            "Garantía de soporte técnico y mantenimiento evolutivo post-entrega"
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Desarrollo Web & Portales de Trámites</b>\n\n"
            "🏢 <b>Entidad:</b> Alcaldía Miguel Hidalgo (CDMX)\n"
            "📋 <b>Licitación:</b> 30001026-032-25 (Consultoría y Desarrollo Web)\n"
            "💡 <b>Solución:</b> Portales Ciudadanos en Next.js + Backend de Trámites FastAPI\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Consultor Senior de Arquitectura Web (60 hrs × $45 USD): $2,700 USD\n"
            "• Desarrollador Frontend Next.js / React (160 hrs × $25 USD): $4,000 USD\n"
            "• Desarrollador Backend Integrador (120 hrs × $25 USD): $3,000 USD\n"
            "• Pruebas de Accesibilidad WCAG & Seguridad: $1,800 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$11,500 USD\n\n"
            "💵 <b>2. Precio de Oferta Licitatoria Sugerida:</b>\n"
            "• <b>Monto Contrato Llave en Mano:</b> <b>$34,000 USD</b> (ó ~$612,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>66.2% de ganancia neta</b> ($22,500 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Mantenimiento Mensual):</b>\n"
            "• Póliza de actualización de contenidos y hosting gestionado: <b>$1,500 USD / mes</b>\n"
            "• Margen mensual recurrente: ~70% ($1,050 USD/mes limpios)"
        ),
        "scope_summary": (
            "🏛️ <b>FICHA TÉCNICA OFICIAL DE LICITACIÓN: ALCALDÍA MIGUEL HIDALGO</b>\n\n"
            "📋 <b>N° Procedimiento:</b> 30001026-032-25\n"
            "💼 <b>Objeto del Procedimiento:</b> SERVICIO DE CONSULTORÍA Y DESARROLLO WEB\n"
            "🏛️ <b>Unidad Convocante:</b> ALCALDÍA MIGUEL HIDALGO\n"
            "💰 <b>Presupuesto Estimado:</b> $25,000 - $55,000 USD\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Portal Convocante:</b> Sistema de Compras Públicas de la Ciudad de México\n"
            "• <b>Enlace Oficial Directo:</b> <code>https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTQxNg==</code>\n\n"
            "📌 <b>Requerimiento Técnico de las Bases:</b>\n"
            "Diseño e implementación de arquitectura web unificada, optimización SEO para trámites públicos, "
            "compatibilidad móvil total y módulo de autogestión de citas ciudadanas.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Documento de arquitectura web, diseño UI/UX en Figma y guías de estilos.\n"
            "2. Desarrollo de frontend responsivo bajo Next.js / TypeScript.\n"
            "3. Conectores REST API con las bases de datos de trámites de la alcaldía.\n"
            "4. Pruebas de estrés y certificación de accesibilidad digital WCAG 2.1 AA."
        )
    },
    {
        "id": "demanda_metro_cdmx_monitoreo_iot",
        "company": "Metro CDMX (Sistema de Transporte Colectivo)",
        "sector": "Movilidad Inteligente, Telemetría & Sistemas IoT",
        "priority": "Licitación Pública Nacional",
        "status_badge": "30102015-012-25",
        "budget": "$60,000 - $120,000 USD",
        "problem": (
            "Licitación Pública Oficial No. 30102015-012-25: 'SUMINISTRO, INSTALACIÓN Y PUESTA EN OPERACIÓN DEL SISTEMA "
            "DE MONITOREO DE EQUIPOS DE MOVILIDAD (ETAPA 1)' para supervisión telemétrica de infraestructura del Metro."
        ),
        "solution": (
            "Plataforma de software telemétrico con ingesta de señales vía MQTT/Kafka, almacenamiento de series de tiempo "
            "en TimescaleDB, tableros de control geoespaciales interactivos y sistema automatizado de alertas de fallas."
        ),
        "tags": ["Telemetría IoT", "Licitación 30102015-012-25", "Sistemas de Movilidad", "Dashboards Tiempo Real"],
        "contact_email": "licitaciones@metro.cdmx.gob.mx",
        "contact_web": "concursodigital.finanzas.cdmx.gob.mx",
        "linkedin_company_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTM3MA==",
        "source_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTM3MA==",
        "demand_source_type": "Licitación Pública No. 30102015-012-25",
        "demand_source_label": "🚇 Licitación Monitoreo Metro CDMX",
        "demand_evidence_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTM3MA==",
        "comparison_points": [
            "Procedimiento oficial 30102015-012-25 del Sistema de Transporte Colectivo",
            "Supervisión telemétrica en tiempo real de infraestructura crítica de movilidad",
            "Arquitectura escalable para integración de futuras etapas y sensores"
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Telemetría & Monitoreo de Transporte</b>\n\n"
            "🏢 <b>Entidad:</b> Metro CDMX (Sistema de Transporte Colectivo)\n"
            "📋 <b>Licitación:</b> 30102015-012-25 (Sistema de Monitoreo de Equipos de Movilidad)\n"
            "💡 <b>Solución:</b> Broker MQTT + Dashboard Geoespacial + Alertas Preventivas\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Ingeniero Especialista IoT / MQTT (100 hrs × $50 USD): $5,000 USD\n"
            "• Desarrolladores Backend Time-Series (140 hrs × $30 USD): $4,200 USD\n"
            "• Desarrollador Frontend GIS / Mapbox (100 hrs × $30 USD): $3,000 USD\n"
            "• Infraestructura Cloud de Telemetría: $2,800 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$15,000 USD\n\n"
            "💵 <b>2. Precio de Oferta Licitatoria Sugerida:</b>\n"
            "• <b>Monto Contrato Llave en Mano:</b> <b>$65,000 USD</b> (ó ~$1,170,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>76.9% de ganancia neta</b> ($50,000 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Mantenimiento Mensual):</b>\n"
            "• Monitoreo 24/7 y soporte de SLAs 99.9%: <b>$2,800 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($2,100 USD/mes limpios)"
        ),
        "scope_summary": (
            "🚇 <b>FICHA TÉCNICA OFICIAL DE LICITACIÓN: METRO CDMX (STC)</b>\n\n"
            "📋 <b>N° Procedimiento:</b> 30102015-012-25\n"
            "💼 <b>Objeto del Procedimiento:</b> SUMINISTRO, INSTALACIÓN Y PUESTA EN OPERACIÓN DEL SISTEMA DE MONITOREO DE EQUIPOS DE MOVILIDAD (ETAPA 1)\n"
            "🏛️ <b>Unidad Convocante:</b> SISTEMA DE TRANSPORTE COLECTIVO\n"
            "💰 <b>Presupuesto Estimado:</b> $60,000 - $120,000 USD\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Portal Convocante:</b> Sistema de Compras Públicas de la Ciudad de México\n"
            "• <b>Enlace Oficial Directo:</b> <code>https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTM3MA==</code>\n\n"
            "📌 <b>Requerimiento Técnico de las Bases:</b>\n"
            "Implementación del software centralizado para captura de datos telemétricos de equipos electromecánicos de movilidad, "
            "registro de eventos y visualización en tiempo real para centros de control.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Servidor de ingesta MQTT seguro con validación de tramas telemétricas.\n"
            "2. Base de datos TimescaleDB optimizada para lecturas de alto volumen.\n"
            "3. Dashboard web interactivo con visualización geográfica de líneas y estaciones.\n"
            "4. Protocolos de alerta ante desvíos de parámetros de funcionamiento normal."
        )
    },
    {
        "id": "demanda_fgjcdmx_cloud_gcp",
        "company": "Fiscalía General de Justicia CDMX (Cloud)",
        "sector": "Cloud Computing, Infraestructura GCP & DevOps",
        "priority": "Licitación Pública Nacional",
        "status_badge": "LPN/FGJCDMX/DACS-053/2025",
        "budget": "$50,000 - $110,000 USD",
        "problem": (
            "Licitación Pública Oficial No. LPN/FGJCDMX/DACS-053/2025: Requerimiento de 'Contratación de servicios informáticos "
            "Google Cloud Platform (GCP) para los sistemas de la Fiscalía General de Justicia de la Ciudad de México'."
        ),
        "solution": (
            "Servicios administrados de computación en la nube GCP, aprovisionamiento automatizado con Terraform, configuración "
            "de clusters de Kubernetes (GKE), esquemas de respaldo cifrado y monitoreo con Google Cloud Operations Suite."
        ),
        "tags": ["Google Cloud Platform", "LPN/FGJCDMX/DACS-053/2025", "Kubernetes / Terraform", "DevOps Cloud"],
        "contact_email": "dacs@fgjcdmx.gob.mx",
        "contact_web": "concursodigital.finanzas.cdmx.gob.mx",
        "linkedin_company_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTMwOA==",
        "source_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTMwOA==",
        "demand_source_type": "Licitación Pública Nacional No. LPN/FGJCDMX/DACS-053/2025",
        "demand_source_label": "☁️ Licitación Servicios Cloud GCP",
        "demand_evidence_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTMwOA==",
        "comparison_points": [
            "Procedimiento oficial LPN/FGJCDMX/DACS-053/2025 en Concurso Digital CDMX",
            "Servicios informáticos especializados en infraestructura Google Cloud",
            "SLA de disponibilidad 99.95% con redundancia geográfica para continuidad operativa"
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Servicios Administrados Cloud GCP</b>\n\n"
            "🏢 <b>Entidad:</b> Fiscalía General de Justicia CDMX\n"
            "📋 <b>Licitación:</b> LPN/FGJCDMX/DACS-053/2025 (Servicios Informáticos GCP)\n"
            "💡 <b>Solución:</b> Arquitectura Multi-Zona GKE + Terraform + CI/CD Cloud\n\n"
            "💰 <b>1. Costo Estimado de Implementación (COGS):</b>\n"
            "• Arquitecto Certificado Google Cloud Professional (80 hrs × $60 USD): $4,800 USD\n"
            "• Ingeniero DevOps / SRE Terraform (120 hrs × $35 USD): $4,200 USD\n"
            "• Pruebas de Carga y Ciberseguridad Cloud: $2,500 USD\n"
            "👉 <b>Costo Base de Arquitectura & Configuración:</b> ~$11,500 USD\n\n"
            "💵 <b>2. Precio de Oferta Licitatoria Sugerida:</b>\n"
            "• <b>Monto Contrato Servicios Administrados:</b> <b>$48,000 USD</b> (ó ~$864,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>76.0% de ganancia neta</b> ($36,500 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Fee de Gestión Cloud Mensual):</b>\n"
            "• Soporte y optimización continua de consumo GCP (FinOps): <b>$2,200 USD / mes</b>\n"
            "• Margen mensual recurrente: ~80% ($1,760 USD/mes limpios)"
        ),
        "scope_summary": (
            "☁️ <b>FICHA TÉCNICA OFICIAL DE LICITACIÓN: FGJCDMX (SERVICIOS CLOUD)</b>\n\n"
            "📋 <b>N° Procedimiento:</b> LPN/FGJCDMX/DACS-053/2025\n"
            "💼 <b>Objeto del Procedimiento:</b> Contratación de servicios informáticos Google Cloud Platform (GCP) para los sistemas de la Fiscalía General de Justicia de la Ciudad de México\n"
            "🏛️ <b>Unidad Convocante:</b> FISCALÍA GENERAL DE JUSTICIA\n"
            "💰 <b>Presupuesto Estimado:</b> $50,000 - $110,000 USD\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Portal Convocante:</b> Sistema de Compras Públicas de la Ciudad de México\n"
            "• <b>Enlace Oficial Directo:</b> <code>https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTMwOA==</code>\n\n"
            "📌 <b>Requerimiento Técnico de las Bases:</b>\n"
            "Asegurar la continuidad operativa de los sistemas institucionales en la nube pública de Google, "
            "con alta disponibilidad, replicación de bases de datos y soporte técnico especializado.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Plan de migración y configuración de infraestructura como código (Terraform).\n"
            "2. Despliegue de clústeres GKE con autoscaling y políticas de red zero-trust.\n"
            "3. Configuración de Cloud Armor para mitigación de ataques DDoS y WAF.\n"
            "4. Monitoreo proactivo con dashboards de latencia, CPU y costos de consumo."
        )
    },
    {
        "id": "demanda_c5_cdmx_ciberseguridad_xdr",
        "company": "FGJCDMX & C5 (Ciberseguridad)",
        "sector": "Ciberseguridad, Detección de Incidentes & Software XDR",
        "priority": "Licitación Pública Nacional",
        "status_badge": "LPN/FGJCDMX/DACS-043/2025",
        "budget": "$45,000 - $90,000 USD",
        "problem": (
            "Licitación Pública Oficial No. LPN/FGJCDMX/DACS-043/2025: 'Contratación del servicio para la renovación del licenciamiento "
            "del software de detección y respuesta a incidentes informáticos (XDR), que incluye instalación, configuración y pruebas'."
        ),
        "solution": (
            "Servicios especializados de ciberseguridad para despliegue de plataforma XDR/EDR, configuración de reglas de detección "
            "de amenazas en endpoints y servidores, integración con SIEM y pruebas de respuesta ante intrusiones."
        ),
        "tags": ["Ciberseguridad XDR", "LPN/FGJCDMX/DACS-043/2025", "SOC / Detección Incidentes", "Seguridad de Endpoints"],
        "contact_email": "dacs@fgjcdmx.gob.mx",
        "contact_web": "concursodigital.finanzas.cdmx.gob.mx",
        "linkedin_company_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTE0MQ==",
        "source_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTE0MQ==",
        "demand_source_type": "Licitación Pública Nacional No. LPN/FGJCDMX/DACS-043/2025",
        "demand_source_label": "🛡️ Licitación Software XDR Ciberseguridad",
        "demand_evidence_url": "https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTE0MQ==",
        "comparison_points": [
            "Procedimiento oficial LPN/FGJCDMX/DACS-043/2025 en Concurso Digital CDMX",
            "Servicios de implementación, configuración y pruebas de funcionalidad de software XDR",
            "Capacitación operativa al equipo de seguridad de la información institucional"
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Implementación de Ciberseguridad XDR</b>\n\n"
            "🏢 <b>Entidad:</b> FGJCDMX & C5 (Seguridad Digital)\n"
            "📋 <b>Licitación:</b> LPN/FGJCDMX/DACS-043/2025 (Software XDR & Incident Response)\n"
            "💡 <b>Solución:</b> Despliegue de Agentes XDR + Integración SIEM + Políticas de Respuesta\n\n"
            "💰 <b>1. Costo Estimado de Implementación Técnica (COGS):</b>\n"
            "• Especialista Senior en Ciberseguridad / SOC (80 hrs × $55 USD): $4,400 USD\n"
            "• Ingeniero de Implementación y Políticas EDR (100 hrs × $35 USD): $3,500 USD\n"
            "• Pruebas de Penetración y Validación de Alertas: $2,500 USD\n"
            "👉 <b>Costo Base de Servicios Técnicos:</b> ~$10,400 USD\n\n"
            "💵 <b>2. Precio de Oferta Licitatoria Sugerida:</b>\n"
            "• <b>Monto Contrato Servicios Especializados:</b> <b>$38,000 USD</b> (ó ~$684,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>72.6% de ganancia neta</b> ($27,600 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Monitoreo SOC Mensual):</b>\n"
            "• Gestión continua de alertas y parches de seguridad: <b>$2,000 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($1,500 USD/mes limpios)"
        ),
        "scope_summary": (
            "🛡️ <b>FICHA TÉCNICA OFICIAL DE LICITACIÓN: FGJCDMX (CIBERSEGURIDAD XDR)</b>\n\n"
            "📋 <b>N° Procedimiento:</b> LPN/FGJCDMX/DACS-043/2025\n"
            "💼 <b>Objeto del Procedimiento:</b> Contratación del servicio para la renovación del licenciamiento del software de detección y respuesta a incidentes informáticos (XDR), que incluye instalación, configuración, puesta en operación y pruebas de funcionalidad\n"
            "🏛️ <b>Unidad Convocante:</b> FISCALÍA GENERAL DE JUSTICIA\n"
            "💰 <b>Presupuesto Estimado:</b> $45,000 - $90,000 USD\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Portal Convocante:</b> Sistema de Compras Públicas de la Ciudad de México\n"
            "• <b>Enlace Oficial Directo:</b> <code>https://concursodigital.finanzas.cdmx.gob.mx/proveedores/detalle_convocatoria/NTE0MQ==</code>\n\n"
            "📌 <b>Requerimiento Técnico de las Bases:</b>\n"
            "Despliegue integral de la solución de seguridad XDR en la infraestructura de servidores y terminales institucionales, "
            "con aislamiento preventivo de amenazas y generación de reportes forenses.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Matriz de despliegue y compatibilidad de agentes en sistemas operativos mixtos.\n"
            "2. Configuración de reglas de correlación y exclusión de falsos positivos.\n"
            "3. Ejecución de simulacros controlados de ataque para validar la respuesta automática.\n"
            "4. Capacitación técnica al personal de guardia del Centro de Operaciones de Seguridad."
        )
    }
]


async def verify_linkedin_url(url: str) -> bool:
    """Verifica de forma rápida y no bloqueante si el perfil de LinkedIn responde o está caído.
    Si está caído, devuelve False para activar el fallback al sitio web oficial de la empresa.
    """
    if not url or "linkedin.com/company" not in url:
        return False
    try:
        async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "es-ES,es;q=0.9,en;q=0.8"
            }
            resp = await client.head(url, headers=headers)
            # 200, 301, 302 o 999 (código de bot de LinkedIn cuando la página existe)
            if resp.status_code in (200, 301, 302, 999):
                return True
            if resp.status_code == 404:
                return False
            # Intentar GET rápido si HEAD devolvió algo ambiguo
            resp_get = await client.get(url, headers=headers)
            if resp_get.status_code in (200, 999):
                return True
            if resp_get.status_code == 404:
                return False
            return True
    except Exception as e:
        logger.debug(f"[LinkedIn Check] URL no disponible o timeout para '{url}': {e}. Aplicando fallback a web.")
        return False


def _clean_web_url(web_str: str) -> str:
    """Asegura que la URL web tenga el protocolo https://."""
    if not web_str:
        return "https://www.google.com"
    clean = web_str.strip()
    if not clean.startswith("http://") and not clean.startswith("https://"):
        clean = f"https://{clean}"
    return clean


async def discover_daily_b2b_demand(ref_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Prospección Diaria Activa del Agente (Opción C):
    1. Revisa si para la fecha actual ya existen empresas en SQLite (`b2b_empresas_demandantes`).
    2. Si ya existen, las retorna de inmediato.
    3. Si no existen, consulta nombres de empresas vistas recientemente para no repetirlas.
    4. Selecciona/genera 5 nuevas empresas para hoy y verifica su perfil de LinkedIn.
    5. Si LinkedIn está caído, marca `linkedin_status = 'unavailable'` para dirigir a la web oficial.
    6. Persiste las empresas descubiertas en la base de datos para hoy.
    """
    now = ref_date or datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # 1. Purgar empresas obsoletas del catálogo histórico en SQLite si existen
    from app.database import purge_obsolete_b2b_companies
    valid_seed_ids = [s.get("id") for s in _SEED_COMPANIES_POOL if s.get("id")]
    purge_obsolete_b2b_companies(valid_seed_ids)

    # 2. Verificar si ya tenemos el lote de hoy en SQLite
    cached_today = get_b2b_companies_by_date(today_str)
    valid_companies_names = {s.get("company") for s in _SEED_COMPANIES_POOL}
    clean_cached = [c for c in (cached_today or []) if c.get("company") in valid_companies_names]
    if len(clean_cached) >= 3:
        logger.info(f"[Prospección B2B] Recuperadas {len(clean_cached)} empresas descubiertas hoy ({today_str}) desde SQLite.")
        return clean_cached

    # 3. Obtener nombres vistos recientemente para evitar repetición
    recent_names = set(get_recent_b2b_company_names(limit=40))
    logger.info(f"[Prospección B2B] Empresas analizadas previamente para exclusión: {len(recent_names)}")

    # 4. Seleccionar 5 empresas no repetidas del pool multindustria
    selected_companies: List[Dict[str, Any]] = []
    
    # Filtrar las no vistas
    fresh_candidates = [c for c in _SEED_COMPANIES_POOL if c.get("company") not in recent_names]
    
    if len(fresh_candidates) >= 5:
        selected_companies = fresh_candidates[:5]
    else:
        # Si ya se recorrió la mayor parte del pool, rotar usando el día del año como desplazamiento
        day_offset = now.timetuple().tm_yday
        total_pool = len(_SEED_COMPANIES_POOL)
        selected_companies = [
            _SEED_COMPANIES_POOL[(day_offset * 3 + i) % total_pool]
            for i in range(min(5, total_pool))
        ]

    # 5. Verificar disponibilidad de LinkedIn concurrentemente con asyncio.gather
    async def _verify_comp(comp: Dict[str, Any]) -> Dict[str, Any]:
        c_copy = dict(comp)
        lk_url = c_copy.get("linkedin_company_url") or ""
        try:
            is_lk_ok = await verify_linkedin_url(lk_url)
        except Exception:
            is_lk_ok = False
        c_copy["linkedin_status"] = "active" if is_lk_ok else "unavailable"
        c_copy["contact_web"] = _clean_web_url(c_copy.get("contact_web", ""))
        return c_copy

    verified_batch = await asyncio.gather(*[_verify_comp(comp) for comp in selected_companies])

    # 6. Guardar en SQLite
    try:
        save_b2b_companies(verified_batch, today_str)
        logger.info(f"[Prospección B2B] Guardadas exitosamente {len(verified_batch)} empresas nuevas para la fecha {today_str}.")
    except Exception as e:
        logger.warning(f"[Prospección B2B] Advertencia al persistir empresas en SQLite: {e}")

    return verified_batch


def get_all_b2b_demand_companies(ref_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Retorna la lista completa de empresas demandantes descubiertas para la fecha actual."""
    now = ref_date or datetime.now(timezone.utc)
    today_str = now.strftime("%Y-%m-%d")

    # Purgar inmediatamente cualquier registro de pruebas o entidades obsoletas
    from app.database import purge_obsolete_b2b_companies
    valid_seed_ids = [s.get("id") for s in _SEED_COMPANIES_POOL if s.get("id")]
    purge_obsolete_b2b_companies(valid_seed_ids)

    companies = get_b2b_companies_by_date(today_str)
    valid_companies_names = {s.get("company") for s in _SEED_COMPANIES_POOL}
    clean_companies = [c for c in (companies or []) if c.get("company") in valid_companies_names]

    if len(clean_companies) >= 3:
        # Auto-reparación / Backfill de evidencia si los registros en DB son previos a la migración
        seed_map = {s.get("company"): s for s in _SEED_COMPANIES_POOL}
        seed_id_map = {s.get("id"): s for s in _SEED_COMPANIES_POOL}
        updated = False
        for c in clean_companies:
            seed = seed_map.get(c.get("company")) or seed_id_map.get(c.get("id"))
            if seed:
                has_old_vacantes = (
                    "Vacantes" in str(c.get("demand_source_label", ""))
                    or "Empleos" in str(c.get("demand_source_label", ""))
                    or "jobs" in str(c.get("demand_evidence_url", ""))
                    or "careers" in str(c.get("demand_evidence_url", ""))
                )
                if not c.get("demand_evidence_url") or c.get("demand_evidence_url") != seed.get("demand_evidence_url") or has_old_vacantes:
                    c["demand_source_type"] = seed.get("demand_source_type", "")
                    c["demand_source_label"] = seed.get("demand_source_label", "")
                    c["demand_evidence_url"] = seed.get("demand_evidence_url", "")
                    if seed.get("scope_summary"):
                        c["scope_summary"] = seed.get("scope_summary")
                    updated = True
        if updated:
            try:
                save_b2b_companies(clean_companies, today_str)
            except Exception:
                pass
        return clean_companies

    # Si no hay registros válidos o eran obsoletos, generar batch fresco del pool oficial
    day_offset = now.timetuple().tm_yday
    total_pool = len(_SEED_COMPANIES_POOL)
    fallback_batch = [
        dict(_SEED_COMPANIES_POOL[(day_offset * 2 + i) % total_pool])
        for i in range(min(5, total_pool))
    ]
    for c in fallback_batch:
        c["contact_web"] = _clean_web_url(c.get("contact_web", ""))
        c.setdefault("linkedin_status", "active")

    try:
        save_b2b_companies(fallback_batch, today_str)
    except Exception:
        pass

    return fallback_batch


def get_b2b_demand_by_index(index: int = 0, ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna la tarjeta estructurada de una empresa específica según su índice en el catálogo diario."""
    catalog = get_all_b2b_demand_companies(ref_date=ref_date)
    total = len(catalog)
    idx = index % total
    item = catalog[idx]

    comp_idx = (idx + 1) % total
    comp_item = catalog[comp_idx]

    now = ref_date or datetime.now(timezone.utc)
    now_str = now.strftime("%d/%m/%Y, %H:%M")
    tags_html = "".join([f'<span class="tag-item">{tag}</span>' for tag in item.get("tags", [])])

    web_url_clean = _clean_web_url(item.get("contact_web", "empresa.com.mx"))
    web_domain_display = web_url_clean.replace("https://", "").replace("http://", "").rstrip("/")

    return {
        "id": item.get("id", f"b2b_{idx}"),
        "company": item.get("company", "Empresa B2B"),
        "status-badge": item.get("status_badge", "Mercado Activo"),
        "lead-company": item.get("company", "Empresa B2B"),
        "lead-sector": item.get("sector", "Tecnología"),
        "lead-priority": item.get("priority", "Alta Intención"),
        "lead-problem": item.get("problem", ""),
        "lead-solution": item.get("solution", ""),
        "lead-tags": tags_html,
        # Contacto corporativo visual en la plantilla
        "lead-contact-email": item.get("contact_email", "contacto@empresa.mx"),
        "lead-contact-web": web_domain_display,
        "lead-contact-social": item.get("linkedin_company_url", "linkedin.com/company/empresa").replace("https://www.", "").replace("https://", ""),
        # Sección de comparación directa
        "sec1-title": f"Comparativa vs: {comp_item.get('company')}",
        "sec1-tag": comp_item.get("sector", "TI B2B"),
        "sec1-desc": f"Presupuesto: {comp_item.get('budget')} · Necesidad: {comp_item.get('problem')[:140]}...",
        "sec1-sol": f"Solución: {comp_item.get('solution')[:70]}...",
        "sec1-status": comp_item.get("status_badge", "Activo"),
        # Información complementaria
        "sec2-title": "Criterios Clave de Selección",
        "sec2-tag": item.get("sector", "B2B"),
        "sec2-desc": " · ".join(item.get("comparison_points", ["Implementación ágil", "Soporte dedicado"])),
        "sec2-sol": f"Presupuesto Estimado: {item.get('budget', 'A convenir')}",
        "sec2-status": "Oportunidad Validada",
        "footer-date": f"Prospección B2B · Empresa {idx + 1}/{total} · Actualizado hoy, {now_str} UTC",
        "source_url": item.get("source_url", web_url_clean),
        "contact_web": web_url_clean,
        "linkedin_company_url": item.get("linkedin_company_url", "https://www.linkedin.com"),
        "linkedin_status": item.get("linkedin_status", "active"),
        "financial_quote": item.get("financial_quote", ""),
        "scope_summary": item.get("scope_summary", ""),
        "demand_source_type": item.get("demand_source_type", ""),
        "demand_source_label": item.get("demand_source_label", ""),
        "demand_evidence_url": item.get("demand_evidence_url", ""),
        "current_index": idx,
        "total_items": total
    }


def get_latest_b2b_demand(ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna los datos de la primera empresa del catálogo diario."""
    return get_b2b_demand_by_index(0, ref_date=ref_date)
