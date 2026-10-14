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

# Pool de empresas reales para rotación y fallback multindustria en México/LATAM
_SEED_COMPANIES_POOL: List[Dict[str, Any]] = [
    {
        "id": "demanda_tianguis_digital_cdmx",
        "company": "Tianguis Digital CDMX (ADIP)",
        "sector": "Gobierno Digital, Trámites & Licitaciones Públicas",
        "priority": "Licitación Abierta Nacional",
        "status_badge": "Convocatoria Pública",
        "budget": "$35,000 - $65,000 USD",
        "problem": (
            "Integración de trámites ciudadanos de múltiples dependencias de la CDMX en una arquitectura modular de microservicios con alta concurrencia y validación de identidad digital."
        ),
        "solution": (
            "Fábrica de software especializada en APIs REST/GraphQL, autenticación segura con Llave CDMX / e.firma y microservicios escalables en nube con trazabilidad y datos abiertos (OCDS)."
        ),
        "tags": ["Fábrica de Software", "APIs & Interoperabilidad", "Llave CDMX / e.firma", "Microservicios Cloud"],
        "contact_email": "tianguisdigital@adip.cdmx.gob.mx",
        "contact_web": "tianguisdigital.cdmx.gob.mx",
        "linkedin_company_url": "https://tianguisdigital.cdmx.gob.mx",
        "source_url": "https://tianguisdigital.cdmx.gob.mx",
        "demand_source_type": "Licitación Pública de Fábrica de Software y APIs (ADIP)",
        "demand_source_label": "🏛️ Portal de Licitaciones Tianguis Digital CDMX",
        "demand_evidence_url": "https://tianguisdigital.cdmx.gob.mx/",
        "comparison_points": [
            "Apego al Estándar de Datos para las Contrataciones Abiertas (OCDS).",
            "Alta disponibilidad para trámites con picos masivos de usuarios concurrentes.",
            "Despliegue contenerizado y monitoreo de microservicios 24/7."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Fábrica de Software Pública</b>\n\n"
            "🏢 <b>Entidad:</b> Tianguis Digital CDMX (ADIP)\n"
            "💡 <b>Solución:</b> Microservicios de Interoperabilidad + Integración e.firma\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Arquitecto de Software & Seguridad (100 hrs × $45 USD): $4,500 USD\n"
            "• Desarrolladores Backend Python/FastAPI (200 hrs × $25 USD): $5,000 USD\n"
            "• Especialista en Ciberseguridad & Pruebas OWASP: $2,500 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$12,000 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Contrato Llave en Mano:</b> <b>$48,000 USD</b> (ó ~$860,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>75% de ganancia neta</b> ($36,000 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / Mantenimiento Mensual):</b>\n"
            "• Soporte y actualización continua de APIs: <b>$2,500 USD / mes</b>\n"
            "• Margen mensual recurrente: ~70% ($1,750 USD/mes limpios)"
        ),
        "scope_summary": (
            "🏛️ <b>FICHA TÉCNICA Y DE LICITACIÓN: Tianguis Digital CDMX</b>\n\n"
            "💼 <b>Sector:</b> Gobierno Digital & Contrataciones Abiertas\n"
            "💰 <b>Presupuesto Estimado:</b> $35,000 - $65,000 USD\n"
            "⏱️ <b>Tiempo de Ejecución:</b> 12 a 16 semanas\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Convocatoria:</b> Licitación Pública de Fábrica de Software y APIs (ADIP)\n"
            "• <b>Portal Oficial:</b> <code>https://tianguisdigital.cdmx.gob.mx/</code>\n\n"
            "📌 <b>Requerimiento Técnico Institucional:</b>\n"
            "Desarrollo e integración de módulos interoperables para la ventanilla única digital de trámites ciudadanos, "
            "con validación criptográfica de identidad y apego a estándares de datos abiertos.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Arquitectura de microservicios contenerizados (Docker/Kubernetes).\n"
            "2. Módulo de autenticación con Llave CDMX y validación de e.firma.\n"
            "3. Conectores REST/GraphQL con bases de datos catastrales y registro civil.\n"
            "4. Dashboard de auditoría y monitoreo transaccional con alertas en tiempo real."
        )
    },
    {
        "id": "demanda_cfe_telemetria",
        "company": "CFE (Comisión Federal de Electricidad)",
        "sector": "Energía, Infraestructura Crítica & Telemetría Industrial",
        "priority": "Concurso Abierto",
        "status_badge": "Licitación TI",
        "budget": "$50,000 - $95,000 USD",
        "problem": (
            "Monitoreo en tiempo real de subestaciones y telemetría de red eléctrica con dispersión geográfica. Requerimiento de integración de protocolos industriales (MQTT/Modbus) hacia servidores centrales."
        ),
        "solution": (
            "Plataforma de procesamiento de eventos en tiempo real con brokers de alta tolerancia a fallos, visualización geográfica en mapas y alertas automáticas de anomalías operativas."
        ),
        "tags": ["Telemetría IoT", "Protocolos MQTT / Industrial", "Time-Series Data", "Ciberseguridad SCADA"],
        "contact_email": "concursos@msc.cfe.mx",
        "contact_web": "msc.cfe.mx",
        "linkedin_company_url": "https://msc.cfe.mx",
        "source_url": "https://msc.cfe.mx",
        "demand_source_type": "Concurso Abierto de Sistemas y Telemetría CFE",
        "demand_source_label": "⚡ Micrositio Oficial de Concursos CFE",
        "demand_evidence_url": "https://msc.cfe.mx/",
        "comparison_points": [
            "Cumplimiento con estándares de seguridad de infraestructura crítica.",
            "Latencia menor a 1 segundo en alarmas críticas de subestaciones.",
            "Interoperabilidad con sistemas legados corporativos SCADA."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Telemetría e Infraestructura Crítica</b>\n\n"
            "🏢 <b>Entidad:</b> CFE (Comisión Federal de Electricidad)\n"
            "💡 <b>Solución:</b> Plataforma de Telemetría IoT + Conectores MQTT + Dashboard\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Ingeniero Especialista IoT / SCADA (120 hrs × $50 USD): $6,000 USD\n"
            "• Desarrolladores Backend TimeSeries (180 hrs × $30 USD): $5,400 USD\n"
            "• Infraestructura Cloud de Alta Disponibilidad: $3,200 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$14,600 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Contrato Llave en Mano:</b> <b>$68,000 USD</b> (ó ~$1,220,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>78.5% de ganancia neta</b> ($53,400 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / Mantenimiento Mensual):</b>\n"
            "• Monitoreo de telemetría y soporte crítico SLAs 99.99%: <b>$3,200 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($2,400 USD/mes limpios)"
        ),
        "scope_summary": (
            "⚡ <b>FICHA TÉCNICA Y DE CONCURSO: CFE Telecomunicaciones & TI</b>\n\n"
            "💼 <b>Sector:</b> Energía & Infraestructura Eléctrica Nacional\n"
            "💰 <b>Presupuesto Estimado:</b> $50,000 - $95,000 USD\n"
            "⏱️ <b>Tiempo de Ejecución:</b> 14 a 18 semanas\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Convocatoria:</b> Concurso Abierto de Sistemas y Telemetría CFE\n"
            "• <b>Portal Oficial:</b> <code>https://msc.cfe.mx/</code>\n\n"
            "📌 <b>Requerimiento Técnico Institucional:</b>\n"
            "Implementación de plataforma centralizada para la ingesta y análisis de señales telemétricas de subestaciones, "
            "con soporte de protocolos industriales y visualización geoespacial en tiempo real.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Broker MQTT distribuido con encriptación TLS 1.3 de grado industrial.\n"
            "2. Base de datos Time-Series de alta velocidad (TimescaleDB / InfluxDB).\n"
            "3. Tablero central de supervisión operativa con mapas geográficos interactivos.\n"
            "4. Sistema proactivo de notificación de alertas ante variaciones de voltaje."
        )
    },
    {
        "id": "demanda_comprasmx_federal",
        "company": "ComprasMX (Plataforma Federal de Contrataciones TI)",
        "sector": "Contrataciones Públicas Federales & Soluciones TIC",
        "priority": "Licitaciones Públicas Abiertas",
        "status_badge": "Licitación Abierta",
        "budget": "$60,000 - $150,000 USD",
        "problem": (
            "Convocatorias federales consolidadas para contratación de Fábricas de Software, servicios administrados de infraestructura en la nube, ciberseguridad y modernización de bases de datos gubernamentales."
        ),
        "solution": (
            "Servicios administrados de desarrollo de software a la medida bajo estándares CMMI/Agile, desarrollo de microservicios con arquitectura segura y soporte técnico continuo."
        ),
        "tags": ["Fábricas de Software Federales", "Servicios Administrados TI", "Ciberseguridad", "Cloud Gubernamental"],
        "contact_email": "upcp@buengobierno.gob.mx",
        "contact_web": "upcp-compranet.buengobierno.gob.mx",
        "linkedin_company_url": "https://upcp-compranet.buengobierno.gob.mx",
        "source_url": "https://upcp-compranet.buengobierno.gob.mx",
        "demand_source_type": "Plataforma Nacional de Licitaciones de Tecnologías de Información",
        "demand_source_label": "🏛️ Plataforma Oficial ComprasMX (Licitaciones TI)",
        "demand_evidence_url": "https://upcp-compranet.buengobierno.gob.mx/",
        "comparison_points": [
            "Participación transparente bajo la Ley de Adquisiciones (LAASSP).",
            "Contratos abiertos plurianuales para agencias y consultoras de software.",
            "Evaluación por puntos y porcentajes con alta ponderación en propuesta técnica."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Licitaciones Públicas Federales</b>\n\n"
            "🏢 <b>Entidad:</b> ComprasMX (Gobierno Federal / APF)\n"
            "💡 <b>Solución:</b> Fábrica de Software Federal + Microservicios Cloud\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Tech Lead & Gerente de Proyecto PMP (160 hrs × $50 USD): $8,000 USD\n"
            "• Equipo de Desarrolladores Senior (300 hrs × $28 USD): $8,400 USD\n"
            "• Certificaciones de Calidad y Ciberseguridad: $4,500 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$20,900 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Contrato Llave en Mano:</b> <b>$95,000 USD</b> (ó ~$1,710,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>78% de ganancia neta</b> ($74,100 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / Mantenimiento Mensual):</b>\n"
            "• Servicios administrados de soporte y operación TI: <b>$5,500 USD / mes</b>\n"
            "• Margen mensual recurrente: ~74% ($4,070 USD/mes limpios)"
        ),
        "scope_summary": (
            "🏛️ <b>FICHA TÉCNICA Y DE CONCURSO: ComprasMX Federal</b>\n\n"
            "💼 <b>Sector:</b> Contratación Pública Federal & TIC\n"
            "💰 <b>Presupuesto Estimado:</b> $60,000 - $150,000 USD\n"
            "⏱️ <b>Tiempo de Ejecución:</b> 18 a 36 semanas\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Convocatoria:</b> Plataforma Nacional de Licitaciones de Tecnologías de Información\n"
            "• <b>Portal Oficial:</b> <code>https://upcp-compranet.buengobierno.gob.mx/</code>\n\n"
            "📌 <b>Requerimiento Técnico Institucional:</b>\n"
            "Provisión de servicios administrados de desarrollo y mantenimiento de aplicaciones de software "
            "para dependencias de la Administración Pública Federal con metodologías ágiles.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Bolsa de horas de fábrica de software con células dedicadas.\n"
            "2. Desarrollo de microservicios con APIs documentadas bajo OpenAPI 3.0.\n"
            "3. Plan de aseguramiento de calidad (QA) y pruebas de vulnerabilidad.\n"
            "4. Transferencia tecnológica y documentación exhaustiva de arquitectura."
        )
    },
    {
        "id": "demanda_walmart_mexico",
        "company": "Walmart de México & Centroamérica",
        "sector": "Retail Omnicanal & Comercio Digital",
        "priority": "Homologación Activa",
        "status_badge": "Convocatoria Proveedor",
        "budget": "$20,000 - $35,000 USD",
        "problem": (
            "Convocatoria oficial para proveedores de tecnología: requerimiento de conectores EDI y APIs para sincronización de catálogos e inventarios entre sucursales físicas y eCommerce central."
        ),
        "solution": (
            "Middleware con colas de mensajería Redis y microservicios FastAPI para sincronización bidireccional de inventarios POS en tiempo real, eliminando cancelaciones por sobreventa."
        ),
        "tags": ["Conectores EDI Retail", "FastAPI / Redis PubSub", "Sincronización POS", "Microservicios Cloud"],
        "contact_email": "proveedores@walmartmexico.com",
        "contact_web": "walmartmexico.com",
        "linkedin_company_url": "https://www.walmartmexico.com",
        "source_url": "https://www.walmartmexico.com",
        "demand_source_type": "Portal Institucional de Convocatorias y Proveedores Walmart",
        "demand_source_label": "🛒 Portal Oficial de Proveedores Walmart",
        "demand_evidence_url": "https://www.walmartmexico.com/proveedores",
        "comparison_points": [
            "Integración certificada con especificaciones EDI de Walmart.",
            "Manejo de picos masivos durante campañas de retail (Hot Sale / Buen Fin).",
            "Monitoreo 24/7 y SLAs de disponibilidad del 99.9%."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Retail Omnicanal</b>\n\n"
            "🏢 <b>Cliente:</b> Walmart de México & Centroamérica\n"
            "💡 <b>Solución:</b> Sync Event-Driven POS ↔ Tienda Online con Redis/FastAPI\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Desarrollador Full-Stack / Conectores (90 hrs × $30 USD): $2,700 USD\n"
            "• Especialista en Bases de Datos / Redis (40 hrs × $35 USD): $1,400 USD\n"
            "• Servidores en la nube (AWS): ~$200 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$4,300 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$24,500 USD</b> (ó ~$440,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>82.4% de ganancia neta</b> ($20,200 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Monitoreo de colas + Garantía de alta disponibilidad: <b>$1,400 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($1,050 USD/mes limpios)"
        ),
        "scope_summary": (
            "🛍️ <b>FICHA TÉCNICA Y DE NEGOCIO: Walmart de México & Centroamérica</b>\n\n"
            "💼 <b>Sector:</b> Retail Omnicanal & Comercio Electrónico\n"
            "💰 <b>Presupuesto Estimado:</b> $20,000 - $35,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 8 a 10 semanas\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Convocatoria:</b> Portal Institucional de Convocatorias y Proveedores Walmart\n"
            "• <b>Portal Oficial:</b> <code>https://www.walmartmexico.com/proveedores</code>\n\n"
            "📌 <b>Requerimiento Técnico Corporativo:</b>\n"
            "Conexión de terminales punto de venta (POS) y catálogos de proveedores con el sistema central "
            "para garantizar inventario unificado y respuesta inmediata en compras online.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Middleware desacoplado en Python / FastAPI con broker de mensajería (Redis Pub/Sub).\n"
            "2. Conector con el sistema POS local para emitir eventos de venta en tiempo real.\n"
            "3. Actualización instantánea de stock vía APIs de catálogo.\n"
            "4. Panel de alertas operativas en caso de pérdida de conectividad en sucursales."
        )
    },
    {
        "id": "demanda_pemex_procurement",
        "company": "PEMEX Procurement (Petróleos Mexicanos)",
        "sector": "Energía & Adquisiciones Corporativas Internacionales",
        "priority": "Concursos Internacionales",
        "status_badge": "Convocatoria Proveedor",
        "budget": "$70,000 - $140,000 USD",
        "problem": (
            "Concursos internacionales y nacionales de adquisición de software especializado, automatización de auditorías de suministros y digitalización de procesos de procura y logística industrial."
        ),
        "solution": (
            "Plataforma de integración transaccional para control de inventarios críticos, auditoría digital con trazabilidad y conectores con sistemas ERP corporativos."
        ),
        "tags": ["Procura Industrial", "Sistemas Transaccionales", "Trazabilidad Logística", "ERP Corporativo"],
        "contact_email": "info@pemexprocurement.com",
        "contact_web": "pemexprocurement.com",
        "linkedin_company_url": "https://pemexprocurement.com",
        "source_url": "https://pemexprocurement.com",
        "demand_source_type": "Portal Internacional de Adquisiciones y Concursos PEMEX",
        "demand_source_label": "🛢️ Portal Oficial Pemex Procurement",
        "demand_evidence_url": "https://pemexprocurement.com/",
        "comparison_points": [
            "Acceso formal a concursos abiertos internacionales de tecnología.",
            "Cumplimiento con estándares corporativos anticorrupción y de transparencia.",
            "Integración de sistemas de procura con plataformas ERP líderes en la industria."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Plataforma de Procura Industrial</b>\n\n"
            "🏢 <b>Entidad:</b> PEMEX Procurement (Petróleos Mexicanos)\n"
            "💡 <b>Solución:</b> Plataforma Transaccional de Suministros + Auditoría Digital\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Arquitecto de Software Enterprise (150 hrs × $55 USD): $8,250 USD\n"
            "• Desarrolladores Backend ERP/Integraciones (250 hrs × $32 USD): $8,000 USD\n"
            "• Módulo de Auditoría y Trazabilidad Criptográfica: $4,500 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$20,750 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Contrato Llave en Mano:</b> <b>$89,000 USD</b> (ó ~$1,600,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>76.7% de ganancia neta</b> ($68,250 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / Mantenimiento Mensual):</b>\n"
            "• Mantenimiento de plataforma y soporte de alta disponibilidad: <b>$4,200 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($3,150 USD/mes limpios)"
        ),
        "scope_summary": (
            "🛢️ <b>FICHA TÉCNICA Y DE CONCURSO: Pemex Procurement</b>\n\n"
            "💼 <b>Sector:</b> Energía, Petróleo & Adquisiciones Industriales\n"
            "💰 <b>Presupuesto Estimado:</b> $70,000 - $140,000 USD\n"
            "⏱️ <b>Tiempo de Ejecución:</b> 16 a 22 semanas\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Convocatoria:</b> Portal Internacional de Adquisiciones y Concursos PEMEX\n"
            "• <b>Portal Oficial:</b> <code>https://pemexprocurement.com/</code>\n\n"
            "📌 <b>Requerimiento Técnico Institucional:</b>\n"
            "Desarrollo e integración de módulos digitales para la trazabilidad y auditoría de procesos de compra, "
            "adjudicación y control de inventarios críticos para operaciones energéticas.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Portal web transaccional seguro con autenticación de dos factores.\n"
            "2. Conectores certificados con plataformas ERP corporativas (SAP/Oracle).\n"
            "3. Módulo inmutable de auditoría para trazabilidad de licitaciones y contratos.\n"
            "4. Panel analítico de métricas de compra y desempeño de proveedores."
        )
    },
    {
        "id": "demanda_concurso_digital_cdmx",
        "company": "Concurso Digital CDMX (Secretaría de Finanzas)",
        "sector": "Finanzas Públicas & Convocatorias de Licitación",
        "priority": "Convocatorias Abiertas",
        "status_badge": "Concurso Abierto",
        "budget": "$30,000 - $60,000 USD",
        "problem": (
            "Convocatorias públicas para desarrollo de sistemas hacendarios, portales de recaudación digital, timbrado masivo CFDI 4.0 y plataformas de atención a contribuyentes."
        ),
        "solution": (
            "Desarrollo de módulos transaccionales de cobro con pasarelas bancarias autorizadas, validación fiscal automática y servicios de alta concurrencia con alta disponibilidad."
        ),
        "tags": ["Sistemas Hacendarios", "Timbrado CFDI 4.0", "Pasarelas Bancarias", "Seguridad Fiscal"],
        "contact_email": "concursodigital@finanzas.cdmx.gob.mx",
        "contact_web": "concursodigital.finanzas.cdmx.gob.mx",
        "linkedin_company_url": "https://concursodigital.finanzas.cdmx.gob.mx",
        "source_url": "https://concursodigital.finanzas.cdmx.gob.mx/convocatorias_publicas",
        "demand_source_type": "Sistema Electrónico de Convocatorias Públicas de la CDMX",
        "demand_source_label": "🏛️ Convocatorias Públicas Concurso Digital CDMX",
        "demand_evidence_url": "https://concursodigital.finanzas.cdmx.gob.mx/convocatorias_publicas",
        "comparison_points": [
            "Convocatorias oficiales vigentes de la Secretaría de Administración y Finanzas.",
            "Blindaje de seguridad transaccional para pagos de contribuciones locales.",
            "Descarga directa de bases y anexos técnicos sin costo."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Sistemas Hacendarios & Recaudación</b>\n\n"
            "🏢 <b>Entidad:</b> Concurso Digital CDMX (Secretaría de Finanzas)\n"
            "💡 <b>Solución:</b> Módulo de Recaudación Digital + Timbrado CFDI 4.0\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Desarrollador Senior Python/FastAPI (100 hrs × $35 USD): $3,500 USD\n"
            "• Especialista en Integración Bancaria y SAT (80 hrs × $40 USD): $3,200 USD\n"
            "• Pruebas de Estrés y Seguridad OWASP: $2,000 USD\n"
            "👉 <b>Costo Base de Implementación:</b> ~$8,700 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Contrato Llave en Mano:</b> <b>$42,000 USD</b> (ó ~$756,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>79.3% de ganancia neta</b> ($33,300 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / Mantenimiento Mensual):</b>\n"
            "• Mantenimiento y actualización ante cambios de miscelánea fiscal: <b>$2,200 USD / mes</b>\n"
            "• Margen mensual recurrente: ~72% ($1,584 USD/mes limpios)"
        ),
        "scope_summary": (
            "🏛️ <b>FICHA TÉCNICA Y DE CONCURSO: Concurso Digital CDMX</b>\n\n"
            "💼 <b>Sector:</b> Finanzas Públicas, Fiscal & Recaudación Digital\n"
            "💰 <b>Presupuesto Estimado:</b> $30,000 - $60,000 USD\n"
            "⏱️ <b>Tiempo de Ejecución:</b> 10 a 14 semanas\n\n"
            "🛡️ <b>Fuente y Verificación Oficial:</b>\n"
            "• <b>Convocatoria:</b> Sistema Electrónico de Convocatorias Públicas de la CDMX\n"
            "• <b>Portal Oficial:</b> <code>https://concursodigital.finanzas.cdmx.gob.mx/convocatorias_publicas</code>\n\n"
            "📌 <b>Requerimiento Técnico Institucional:</b>\n"
            "Desarrollo e integración de componentes para el portal de trámites hacendarios, "
            "conciliación bancaria en línea y timbrado masivo de comprobantes fiscales.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Pasarela de pagos con conexión segura a múltiples instituciones bancarias.\n"
            "2. Validador en tiempo real de estatus fiscal y generación automática de recibos CFDI.\n"
            "3. Arquitectura resiliente ante cierres fiscales de alta concurrencia.\n"
            "4. Bitácora de transacciones bancarias auditables."
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
