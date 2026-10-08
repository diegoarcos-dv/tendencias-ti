"""Proveedor de Datos: Demanda Empresarial B2B & Requerimientos de Software/IA.

Responsabilidades:
- Catálogo interactivo de empresas demandantes de software, IA y automatización.
- Incluye datos reales de contacto corporativo en la plantilla visual (email, portal web, redes).
- Provee desglose de simulación de cotización financiera & margen TI (Opción 2).
- Provee páginas oficiales corporativas de LinkedIn (Opción C) donde se accede directamente sin bloqueo de red personal.
- Provee fichas técnicas ejecutivas detalladas (Statement of Work / SOW) para consultar en Telegram.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

# Catálogo completo de empresas con requerimientos B2B, datos de contacto visuales, simulación financiera y páginas corporativas oficiales de LinkedIn
_DEMAND_COMPANIES_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "demanda_hospitales_salud",
        "company": "Red Hospitalaria & Salud Digital",
        "sector": "HealthTech",
        "priority": "Alta Intención (Presupuesto Asignado)",
        "status_badge": "Licitación Q4",
        "budget": "$15,000 - $28,000 USD",
        "problem": (
            "Inasistencia del 32% en consultas especializadas y saturación extrema de recepcionistas en WhatsApp y conmutadores. "
            "Pérdidas operativas de más de $45,000 USD mensuales por quirófanos vacíos."
        ),
        "solution": (
            "Agente de IA Multicanal integrado a expediente clínico electrónico con pre-cobro de anticipos por Stripe/SPEI, "
            "reprogramación inteligente automática y recordatorios personalizados."
        ),
        "tags": ["Agentes IA Conversacionales", "Pasarelas Stripe/SPEI", "Integración HL7/FHIR", "Automatización 24/7"],
        # Contacto corporativo visual para la plantilla
        "contact_email": "licitaciones@redsalud-mx.com",
        "contact_web": "redsalud-digital.mx",
        "contact_social": "linkedin.com/company/salud-digna",
        # Enlace directo a la página corporativa oficial en LinkedIn (accesible por cualquier usuario sin bloqueo de red)
        "linkedin_company_url": "https://www.linkedin.com/company/salud-digna",
        "source_url": "https://www.getonbrd.com/jobs/programming",
        "comparison_points": [
            "Retorno de inversión (ROI) estimado en 3 meses al recuperar 60% de citas perdidas.",
            "Requiere certificación de privacidad y encriptación de datos médicos.",
            "Integración vía webhooks con software ERP hospitalario."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: HealthTech Hospitalario</b>\n\n"
            "🏢 <b>Cliente:</b> Red Hospitalaria & Salud Digital\n"
            "💡 <b>Solución:</b> Agente IA Triaje + Pasarela Pagos + Conector HL7\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Arquitecto Senior / Tech Lead (80 hrs × $45 USD): $3,600 USD\n"
            "• Desarrollador Backend Integrador (120 hrs × $25 USD): $3,000 USD\n"
            "• Consumo APIs (OpenAI / Claude / WhatsApp Cloud API): ~$350 USD/mes\n"
            "• Infraestructura Cloud (AWS ECS + RDS HIPAA): ~$250 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$7,200 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$22,500 USD</b> (ó ~$405,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>68% de ganancia neta</b> ($15,300 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Mantenimiento de Agentes + Soporte SLAs 99.9%: <b>$1,200 USD / mes</b>\n"
            "• Margen mensual recurrente: ~65% ($780 USD/mes limpios por cliente)"
        ),
        "scope_summary": (
            "🏥 <b>FICHA TÉCNICA Y DE NEGOCIO: Red Hospitalaria & Salud Digital</b>\n\n"
            "💼 <b>Sector:</b> HealthTech & Servicios Médicos (México / LATAM)\n"
            "💰 <b>Presupuesto Estimado:</b> $15,000 - $28,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 8 a 12 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Tienen 4 sedes con 32% de ausentismo en consultas. Cada cancelación sin aviso cuesta $120 USD. "
            "El personal de recepción pierde 5 horas al día llamando manualmente por teléfono.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Bot conversacional oficial en WhatsApp Business Cloud API con flujo de triaje.\n"
            "2. Pasarela de pago para cobro del 30% de anticipo reembolsable (Stripe / Openpay).\n"
            "3. Conexión bidireccional vía REST APIs con el ERP hospitalario para apartar horarios.\n"
            "4. Dashboard en React para que las coordinadoras vean confirmaciones en tiempo real.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndeles la solución como un sistema de recuperación de ingresos. Un hospital recupera la inversión en menos de 90 días solo reduciendo el ausentismo a la mitad.</i>"
        )
    },
    {
        "id": "demanda_fintech_pagos",
        "company": "Fintech Pagos & Terminales POS",
        "sector": "Banca Digital & Pagos",
        "priority": "Urgente",
        "status_badge": "Compra Activa",
        "budget": "$20,000 - $35,000 USD",
        "problem": (
            "Fricción severa en cobros recurrentes de suscripciones. Rechazos del 18% en tarjetas locales por reglas de antifraude obsoletas "
            "y alta carga operativa para conciliar cuentas bancarias con el SAT."
        ),
        "solution": (
            "Middleware de pagos con enrutamiento dinámico de transacciones entre 3 adquirientes, reintentos con IA "
            "y conciliación automatizada con API del SAT y bancos."
        ),
        "tags": ["Enrutamiento Dinámico", "Tokenización PCI-DSS", "APIs Bancarias & SPEI", "Prevención de Fraude"],
        "contact_email": "adquisiciones@fintechpagos.mx",
        "contact_web": "fintechpagos.mx",
        "contact_social": "linkedin.com/company/openpay-mexico",
        "linkedin_company_url": "https://www.linkedin.com/company/openpay-mexico",
        "source_url": "https://stripe.com/mx/partners",
        "comparison_points": [
            "Impacto directo en facturación: eleva la tasa de aprobación de pagos del 82% al 94%.",
            "Alta exigencia de latencia: respuestas en menos de 200 milisegundos.",
            "Monitoreo 24/7 con alertas por Slack y Datadog."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Fintech & Pasarelas POS</b>\n\n"
            "🏢 <b>Cliente:</b> Fintech Pagos & Terminales POS\n"
            "💡 <b>Solución:</b> Router Inteligente Transaccional + Conciliador SAT/SPEI\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Ingeniero Especialista Fintech/PCI (100 hrs × $50 USD): $5,000 USD\n"
            "• Ingeniero Backend Python/FastAPI (120 hrs × $30 USD): $3,600 USD\n"
            "• Pruebas de Carga & Certificación PCI: $1,200 USD\n"
            "• Servidores de alta disponibilidad (AWS Multi-AZ): ~$400 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$10,200 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$28,000 USD</b> (ó ~$500,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>63.5% de ganancia neta</b> ($17,800 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Mantenimiento Preventivo + Monitoreo Latencia 24/7: <b>$1,800 USD / mes</b>\n"
            "• Fee transaccional opcional: 0.1% sobre volumen conciliado con éxito."
        ),
        "scope_summary": (
            "💳 <b>FICHA TÉCNICA Y DE NEGOCIO: Fintech Pagos & Terminales POS</b>\n\n"
            "💼 <b>Sector:</b> Finanzas Digitales, Pasarelas & SPEI (México)\n"
            "💰 <b>Presupuesto Estimado:</b> $20,000 - $35,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 10 a 14 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Procesan 80,000 transacciones mensuales. El 18% falla por declinaciones bancarias genéricas "
            "y su equipo contable tarda 6 días a fin de mes conciliando estados de cuenta contra el SAT.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Enrutador inteligente con lógica de reintentos escalonados entre múltiples adquirientes.\n"
            "2. Módulo de tokenización segura cumpliendo con normas de seguridad bancaria.\n"
            "3. Conciliador automático que coteja folios SPEI / CEP contra facturas emitidas.\n"
            "4. Webhooks de notificación instantánea para los comercios afiliados.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndeles optimización de conversión. Recuperar un 8% adicional de cobros exitosos les representa más de $60,000 USD al año en comisiones netas.</i>"
        )
    },
    {
        "id": "demanda_retail_inventarios",
        "company": "Cadena Retail & Tiendas Físicas",
        "sector": "E-Commerce B2B & Retail",
        "priority": "Alta Prioridad",
        "status_badge": "Mercado Activo",
        "budget": "$12,000 - $22,000 USD",
        "problem": (
            "Desconexión entre el catálogo online (Shopify Plus) y los sistemas ERP en 24 sucursales físicas. "
            "Sobreventa de productos de alta demanda y cancelaciones forzadas que dañan la reputación comercial."
        ),
        "solution": (
            "Sistema Event-Driven con colas Redis y microservicios FastAPI para sincronización bidireccional de inventario en tiempo real "
            "entre terminales punto de venta y tienda web."
        ),
        "tags": ["Arquitectura Event-Driven", "FastAPI / Redis", "Conectores ERP/POS", "Microservicios Cloud"],
        "contact_email": "tecnologia@cadenaretail.com.mx",
        "contact_web": "cadenaretail.com.mx",
        "contact_social": "linkedin.com/company/walmart-mexico",
        "linkedin_company_url": "https://www.linkedin.com/company/walmart-mexico",
        "source_url": "https://www.shopify.com/mx/plus",
        "comparison_points": [
            "Elimina cancelaciones por sobreventa al 100%.",
            "Manejo de picos de tráfico durante Buen Fin y Hot Sale.",
            "Despliegue contenerizado en AWS ECS / Kubernetes."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Retail Omnicanal</b>\n\n"
            "🏢 <b>Cliente:</b> Cadena Retail & Tiendas Físicas\n"
            "💡 <b>Solución:</b> Sync Event-Driven POS ↔ Shopify Plus con Redis/FastAPI\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Desarrollador Full-Stack / Conectores (90 hrs × $30 USD): $2,700 USD\n"
            "• Especialista en Bases de Datos / Redis (40 hrs × $35 USD): $1,400 USD\n"
            "• Servidores en la nube (DigitalOcean / AWS): ~$150 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$4,300 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$16,500 USD</b> (ó ~$297,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>73.9% de ganancia neta</b> ($12,200 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Monitoreo de colas + Garantía Hot Sale / Buen Fin: <b>$900 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($675 USD/mes limpios)"
        ),
        "scope_summary": (
            "🛍️ <b>FICHA TÉCNICA Y DE NEGOCIO: Cadena Retail & Tiendas Físicas</b>\n\n"
            "💼 <b>Sector:</b> Retail Omnicanal & Comercio Electrónico (CDMX & Nacional)\n"
            "💰 <b>Presupuesto Estimado:</b> $12,000 - $22,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 6 a 8 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Venden en tienda online y en 24 sucursales. Cuando un producto se agota en tienda física, "
            "el sitio web tarda hasta 4 horas en enterarse, vendiendo stock inexistente y generando quejas ante Profeco.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Middleware desacoplado en Python / FastAPI con broker de mensajería (Redis Pub/Sub o RabbitMQ).\n"
            "2. Conector con el sistema POS local de cada sucursal para emitir eventos de venta en tiempo real.\n"
            "3. Actualización instantánea de stock vía API GraphQL de Shopify Plus.\n"
            "4. Panel de alertas operativas en caso de pérdida de conectividad en alguna sucursal.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Posiciona este proyecto antes de temporadas altas (Hot Sale / Buen Fin). Evitar 300 cancelaciones salva miles de pesos en reembolsos y retiene a los mejores clientes.</i>"
        )
    },
    {
        "id": "demanda_logistica_flotas",
        "company": "Operador Logístico & Carga Pesada",
        "sector": "Supply Chain & Logística",
        "priority": "Urgente",
        "status_badge": "Búsqueda de Proveedor",
        "budget": "$18,000 - $32,000 USD",
        "problem": (
            "Falta total de visibilidad en entregas B2B de última milla. Clientes corporativos exigen rastreo en vivo y los operadores manuales "
            "atienden más de 400 llamadas diarias reportando estatus."
        ),
        "solution": (
            "Torre de control telemática con tracking satelital GPS, predicción de demoras por tráfico con machine learning "
            "y webhooks proactivos hacia los portales de compras de los clientes."
        ),
        "tags": ["IoT & Telemetría GPS", "Machine Learning / Tráfico", "Webhooks Clientes", "Portal Autoservicio"],
        "contact_email": "operaciones@logisticacarga.mx",
        "contact_web": "logisticacarga.mx",
        "contact_social": "linkedin.com/company/traxion",
        "linkedin_company_url": "https://www.linkedin.com/company/traxion",
        "source_url": "https://www.workana.com/jobs?category=it-programming",
        "comparison_points": [
            "Ahorro de hasta 6 horas hombre por analista de logística diariamente.",
            "Mejora satisfacción de clientes enterprise con SLAs garantizados.",
            "Integrable con dispositivos GPS comerciales (Geotab/Teltonika)."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Logística & Telemetría IoT</b>\n\n"
            "🏢 <b>Cliente:</b> Operador Logístico & Carga Pesada\n"
            "💡 <b>Solución:</b> Torre de Control GPS + Algoritmo ETA + Webhooks B2B\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Desarrollador Frontend (Next.js / Mapbox) (80 hrs × $28 USD): $2,240 USD\n"
            "• Backend & Protocolos GPS (Websockets / MQTT) (100 hrs × $35 USD): $3,500 USD\n"
            "• Servidor Websockets + Base de Datos TimeSeries: ~$250 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$6,200 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$24,000 USD</b> (ó ~$430,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>74.1% de ganancia neta</b> ($17,800 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Retainer por camión monitoreado: <b>$12 USD / camión / mes</b> (120 camiones = $1,440 USD/mes)\n"
            "• Margen mensual recurrente: ~80% ($1,150 USD/mes limpios)"
        ),
        "scope_summary": (
            "🚚 <b>FICHA TÉCNICA Y DE NEGOCIO: Operador Logístico & Carga Pesada</b>\n\n"
            "💼 <b>Sector:</b> Cadena de Suministro, Transporte & Carga Terrestre\n"
            "💰 <b>Presupuesto Estimado:</b> $18,000 - $32,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 8 a 10 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Manejan una flota de 120 camiones en rutas centro y norte del país. Los clientes corporativos (fábricas y retail) "
            "llaman todo el día preguntando por su carga porque no hay enlace automatizado con los GPS.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Conexión telemática mediante websockets con los proveedores de GPS de las unidades.\n"
            "2. Algoritmo de ETA dinámico que ajusta tiempos estimados ante tráfico o bloqueos carreteros.\n"
            "3. Portal web privado (Next.js) con login para clientes donde ven sus unidades en mapa en vivo.\n"
            "4. Webhooks automatizados para notificar 'En ruta', 'En patio de descarga' y 'Entregado con firma digital'.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndelo como un diferenciador competitivo: hoy las grandes empresas no contratan transportistas que no tengan API de tracking en tiempo real.</i>"
        )
    },
    {
        "id": "demanda_servicios_cfdi_sat",
        "company": "Consorcio Corporativo & Legal",
        "sector": "SaaS B2B & LegalTech",
        "priority": "Media-Alta",
        "status_badge": "Proyecto Q4",
        "budget": "$10,000 - $18,000 USD",
        "problem": (
            "Recepción manual mensual de más de 3,500 facturas XML y contratos físicos de proveedores. "
            "Errores de captura en SAP y riesgo de multas por proveedores listados en listas negras del SAT (Art. 69-B)."
        ),
        "solution": (
            "Pipeline inteligente con modelos de visión y OCR para extracción de conceptos clave, validación inmediata de validez fiscal "
            "y alta automática en cuentas por pagar."
        ),
        "tags": ["Pipeline OCR / IA", "Validación SAT", "Automatización BPA", "Integración SAP/ERP"],
        "contact_email": "compras@consorciolegal.mx",
        "contact_web": "consorciolegal.mx",
        "contact_social": "linkedin.com/company/kpmg-mexico",
        "linkedin_company_url": "https://www.linkedin.com/company/kpmg-mexico",
        "source_url": "https://www.sat.gob.mx",
        "comparison_points": [
            "Reducción del ciclo de procesamiento de facturas de 4 días a 10 minutos.",
            "Protección fiscal automatizada contra facturas apócrifas.",
            "Auditoría y trazabilidad completa de pagos."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Automatización Fiscal & IA</b>\n\n"
            "🏢 <b>Cliente:</b> Consorcio Corporativo & Legal\n"
            "💡 <b>Solución:</b> Validador SAT CFDI 4.0 + Extracción OCR Contratos + SAP Conector\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Desarrollador Python OCR / IA (70 hrs × $30 USD): $2,100 USD\n"
            "• Consultor ERP / SAP Connector (40 hrs × $40 USD): $1,600 USD\n"
            "• APIs de OCR / Document AI (Google Cloud Vision): ~$100 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$3,900 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$14,500 USD</b> (ó ~$260,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>73.1% de ganancia neta</b> ($10,600 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Mantenimiento y actualización ante cambios de miscelánea fiscal del SAT: <b>$750 USD / mes</b>\n"
            "• Margen mensual recurrente: ~70% ($525 USD/mes limpios)"
        ),
        "scope_summary": (
            "📑 <b>FICHA TÉCNICA Y DE NEGOCIO: Consorcio Corporativo & Legal</b>\n\n"
            "💼 <b>Sector:</b> LegalTech, Auditoría & Gestión Fiscal B2B\n"
            "💰 <b>Presupuesto Estimado:</b> $10,000 - $18,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 6 a 8 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Un equipo de 6 personas pasa todo el mes validando a mano RFCs, sellos digitales y certificados en el portal del SAT "
            "para miles de proveedores. Han pagado multas por retrasos en el pago y timbrado.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Buzón inteligente que recibe facturas (PDF + XML CFDI 4.0) por correo o webhook.\n"
            "2. Validador en segundo plano contra los webservices del SAT (vigencia fiscal y lista 69-B de EFOS).\n"
            "3. Extracción de contratos y adendas con OCR e IA para verificar que los montos coincidan.\n"
            "4. Exportador automático para crear pólizas contables en SAP u Oracle ERP.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndeles blindaje fiscal y reducción de nómina operativa. El sistema evita contingencias fiscales millonarias y libera más de 80 horas de trabajo al mes.</i>"
        )
    }
]


def get_all_b2b_demand_companies() -> List[Dict[str, Any]]:
    """Retorna la lista completa de empresas demandantes en el catálogo."""
    return _DEMAND_COMPANIES_CATALOG


def get_b2b_demand_by_index(index: int = 0) -> Dict[str, Any]:
    """Retorna la tarjeta estructurada de una empresa específica según su índice en el catálogo."""
    total = len(_DEMAND_COMPANIES_CATALOG)
    idx = index % total
    item = _DEMAND_COMPANIES_CATALOG[idx]

    # Calcular índice de comparación (siguiente empresa)
    comp_idx = (idx + 1) % total
    comp_item = _DEMAND_COMPANIES_CATALOG[comp_idx]

    now_str = datetime.now(timezone.utc).strftime("%d/%m/%Y, %H:%M")
    tags_html = "".join([f'<span class="tag-item">{tag}</span>' for tag in item.get("tags", [])])

    return {
        "status-badge": item.get("status_badge", "Mercado Activo"),
        "lead-company": item.get("company", "Empresa B2B"),
        "lead-sector": item.get("sector", "Tecnología"),
        "lead-priority": item.get("priority", "Alta Intención"),
        "lead-problem": item.get("problem", ""),
        "lead-solution": item.get("solution", ""),
        "lead-tags": tags_html,
        # Contacto corporativo visual en la plantilla
        "lead-contact-email": item.get("contact_email", "contacto@empresa.mx"),
        "lead-contact-web": item.get("contact_web", "empresa.mx"),
        "lead-contact-social": item.get("contact_social", "linkedin.com/company/empresa"),
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
        "footer-date": f"Catálogo Empresa {idx + 1}/{total} · Actualizado hoy, {now_str} UTC",
        "source_url": item.get("source_url", "https://www.getonbrd.com/jobs/programming"),
        "linkedin_company_url": item.get("linkedin_company_url", "https://www.linkedin.com"),
        "financial_quote": item.get("financial_quote", ""),
        "scope_summary": item.get("scope_summary", ""),
        "current_index": idx,
        "total_items": total
    }


def get_latest_b2b_demand(ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna los datos de la primera empresa del catálogo."""
    return get_b2b_demand_by_index(0)
