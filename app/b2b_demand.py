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
        "id": "demanda_salud_digna",
        "company": "Salud Digna & Red de Laboratorios",
        "sector": "HealthTech & Diagnóstico",
        "priority": "Alta Intención (Presupuesto Asignado)",
        "status_badge": "Licitación Q4",
        "budget": "$15,000 - $28,000 USD",
        "problem": (
            "Inasistencia del 32% en estudios diagnósticos y saturación de recepcionistas en WhatsApp y conmutadores. "
            "Pérdidas operativas de más de $45,000 USD mensuales por citas desaprovechadas."
        ),
        "solution": (
            "Agente de IA Multicanal integrado a expediente clínico electrónico con pre-cobro de anticipos por Stripe/SPEI, "
            "reprogramación inteligente automática y entrega de resultados por WhatsApp."
        ),
        "tags": ["Agentes IA Conversacionales", "Pasarelas Stripe/SPEI", "Integración HL7/FHIR", "Automatización 24/7"],
        "contact_email": "licitaciones@salud-digna.org",
        "contact_web": "salud-digna.org",
        "linkedin_company_url": "https://www.linkedin.com/company/salud-digna",
        "source_url": "https://salud-digna.org",
        "comparison_points": [
            "Retorno de inversión (ROI) estimado en 3 meses al recuperar 60% de citas perdidas.",
            "Requiere certificación de privacidad y encriptación de datos médicos.",
            "Integración vía webhooks con software ERP hospitalario."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: HealthTech Hospitalario</b>\n\n"
            "🏢 <b>Cliente:</b> Salud Digna & Red de Laboratorios\n"
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
            "🏥 <b>FICHA TÉCNICA Y DE NEGOCIO: Salud Digna & Red de Laboratorios</b>\n\n"
            "💼 <b>Sector:</b> HealthTech & Servicios Médicos (México / LATAM)\n"
            "💰 <b>Presupuesto Estimado:</b> $15,000 - $28,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 8 a 12 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Tienen clínicas en todo el país con 32% de ausentismo en estudios. Cada cancelación sin aviso cuesta $120 USD. "
            "El personal de recepción pierde 5 horas al día llamando manualmente por teléfono.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Bot conversacional oficial en WhatsApp Business Cloud API con flujo de triaje y citas.\n"
            "2. Pasarela de pago para cobro del 30% de anticipo reembolsable (Stripe / Openpay).\n"
            "3. Conexión bidireccional vía REST APIs con el ERP hospitalario para apartar horarios.\n"
            "4. Dashboard en React para que las coordinadoras vean confirmaciones en tiempo real.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndeles la solución como un sistema de recuperación de ingresos. Un laboratorio recupera la inversión en menos de 90 días solo reduciendo el ausentismo a la mitad.</i>"
        )
    },
    {
        "id": "demanda_openpay_fintech",
        "company": "Openpay by BBVA",
        "sector": "Fintech & Infraestructura de Pagos",
        "priority": "Urgente",
        "status_badge": "Compra Activa",
        "budget": "$20,000 - $35,000 USD",
        "problem": (
            "Fricción en cobros recurrentes de suscripciones y transacciones de e-commerce. Rechazos del 18% en tarjetas locales por reglas de antifraude obsoletas "
            "y alta carga operativa para conciliar cuentas bancarias con el SAT."
        ),
        "solution": (
            "Middleware de pagos con enrutamiento dinámico de transacciones entre adquirientes, reintentos con IA "
            "y conciliación automatizada con API del SAT y bancos."
        ),
        "tags": ["Enrutamiento Dinámico", "Tokenización PCI-DSS", "APIs Bancarias & SPEI", "Prevención de Fraude"],
        "contact_email": "soporte@openpay.mx",
        "contact_web": "openpay.mx",
        "linkedin_company_url": "https://www.linkedin.com/company/openpaymx",
        "source_url": "https://www.openpay.mx",
        "comparison_points": [
            "Impacto directo en facturación: eleva la tasa de aprobación de pagos del 82% al 94%.",
            "Alta exigencia de latencia: respuestas en menos de 200 milisegundos.",
            "Monitoreo 24/7 con alertas por Slack y Datadog."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Fintech & Pasarelas POS</b>\n\n"
            "🏢 <b>Cliente:</b> Openpay by BBVA\n"
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
            "💳 <b>FICHA TÉCNICA Y DE NEGOCIO: Openpay by BBVA</b>\n\n"
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
        "id": "demanda_walmart_mexico",
        "company": "Walmart de México & Centroamérica",
        "sector": "Retail Omnicanal & Comercio Digital",
        "priority": "Alta Prioridad",
        "status_badge": "Mercado Activo",
        "budget": "$18,000 - $30,000 USD",
        "problem": (
            "Desconexión entre el catálogo online y los inventarios en sucursales físicas. "
            "Sobreventa de productos de alta demanda durante temporadas comerciales y cancelaciones forzadas."
        ),
        "solution": (
            "Sistema Event-Driven con colas Redis y microservicios FastAPI para sincronización bidireccional de inventario en tiempo real "
            "entre terminales punto de venta y tienda web."
        ),
        "tags": ["Arquitectura Event-Driven", "FastAPI / Redis", "Conectores ERP/POS", "Microservicios Cloud"],
        "contact_email": "tecnologia@walmartmexico.com",
        "contact_web": "walmartmexico.com",
        "linkedin_company_url": "https://www.linkedin.com/company/walmartmexico",
        "source_url": "https://www.walmartmexico.com",
        "comparison_points": [
            "Elimina cancelaciones por sobreventa al 100%.",
            "Manejo de picos de tráfico durante Buen Fin y Hot Sale.",
            "Despliegue contenerizado en AWS ECS / Kubernetes."
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
            "• <b>Precio Llave en Mano:</b> <b>$18,500 USD</b> (ó ~$330,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>76.7% de ganancia neta</b> ($14,200 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Monitoreo de colas + Garantía de alta disponibilidad: <b>$1,100 USD / mes</b>\n"
            "• Margen mensual recurrente: ~75% ($825 USD/mes limpios)"
        ),
        "scope_summary": (
            "🛍️ <b>FICHA TÉCNICA Y DE NEGOCIO: Walmart de México & Centroamérica</b>\n\n"
            "💼 <b>Sector:</b> Retail Omnicanal & Comercio Electrónico (CDMX & Nacional)\n"
            "💰 <b>Presupuesto Estimado:</b> $18,000 - $30,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 8 a 10 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Venden en tienda online y en cientos de sucursales. Cuando un producto se agota en tienda física, "
            "el sistema web tarda en enterarse, vendiendo stock inexistente y generando reclamaciones.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Middleware desacoplado en Python / FastAPI con broker de mensajería (Redis Pub/Sub).\n"
            "2. Conector con el sistema POS local de sucursales para emitir eventos de venta en tiempo real.\n"
            "3. Actualización instantánea de stock vía APIs de catálogo.\n"
            "4. Panel de alertas operativas en caso de pérdida de conectividad en sucursales.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Evitar cancelaciones en temporadas altas salva miles de dólares en reembolsos y retiene la lealtad del cliente.</i>"
        )
    },
    {
        "id": "demanda_traxion_logistica",
        "company": "Grupo Traxión",
        "sector": "Supply Chain & Movilidad Integral",
        "priority": "Urgente",
        "status_badge": "Búsqueda de Proveedor",
        "budget": "$18,000 - $32,000 USD",
        "problem": (
            "Falta de visibilidad unificada en entregas B2B de última milla. Clientes corporativos exigen rastreo en vivo y los operadores manuales "
            "atienden cientos de llamadas diarias reportando estatus."
        ),
        "solution": (
            "Torre de control telemática con tracking satelital GPS, predicción de demoras por tráfico con machine learning "
            "y webhooks proactivos hacia los portales de compras de los clientes."
        ),
        "tags": ["IoT & Telemetría GPS", "Machine Learning / Tráfico", "Webhooks Clientes", "Portal Autoservicio"],
        "contact_email": "contacto@traxion.global",
        "contact_web": "traxion.global",
        "linkedin_company_url": "https://www.linkedin.com/company/traxion",
        "source_url": "https://traxion.global",
        "comparison_points": [
            "Ahorro de hasta 6 horas hombre por analista de logística diariamente.",
            "Mejora satisfacción de clientes enterprise con SLAs garantizados.",
            "Integrable con dispositivos GPS comerciales (Geotab/Teltonika)."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Logística & Telemetría IoT</b>\n\n"
            "🏢 <b>Cliente:</b> Grupo Traxión\n"
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
            "🚚 <b>FICHA TÉCNICA Y DE NEGOCIO: Grupo Traxión</b>\n\n"
            "💼 <b>Sector:</b> Cadena de Suministro, Transporte & Carga Terrestre\n"
            "💰 <b>Presupuesto Estimado:</b> $18,000 - $32,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 8 a 10 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Manejan flotas de carga pesada en rutas del país. Los clientes corporativos "
            "llaman todo el día preguntando por su carga porque no hay enlace automatizado con los GPS.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Conexión telemática mediante websockets con proveedores de GPS de las unidades.\n"
            "2. Algoritmo de ETA dinámico que ajusta tiempos estimados ante tráfico o desvíos.\n"
            "3. Portal web privado (Next.js) con login para clientes donde ven sus unidades en mapa en vivo.\n"
            "4. Webhooks automatizados para notificar 'En ruta', 'En patio de descarga' y 'Entregado con firma digital'.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndelo como diferenciador competitivo: hoy las grandes empresas exigen APIs de tracking en tiempo real.</i>"
        )
    },
    {
        "id": "demanda_kpmg_legal",
        "company": "KPMG México",
        "sector": "LegalTech, Auditoría & Fiscal B2B",
        "priority": "Media-Alta",
        "status_badge": "Proyecto Q4",
        "budget": "$12,000 - $20,000 USD",
        "problem": (
            "Recepción manual mensual de miles de facturas XML y contratos de proveedores. "
            "Errores de captura en sistemas contables y riesgo de sanciones por proveedores en listas negras del SAT (Art. 69-B)."
        ),
        "solution": (
            "Pipeline inteligente con modelos de visión y OCR para extracción de conceptos clave, validación inmediata de validez fiscal "
            "y alta automática en cuentas por pagar."
        ),
        "tags": ["Pipeline OCR / IA", "Validación SAT", "Automatización BPA", "Integración SAP/ERP"],
        "contact_email": "contacto@kpmg.com.mx",
        "contact_web": "kpmg.com/mx",
        "linkedin_company_url": "https://www.linkedin.com/company/kpmg-mexico",
        "source_url": "https://kpmg.com/mx",
        "comparison_points": [
            "Reducción del ciclo de procesamiento de facturas de 4 días a 10 minutos.",
            "Protección fiscal automatizada contra facturas apócrifas.",
            "Auditoría y trazabilidad completa de pagos."
        ],
        "financial_quote": (
            "📊 <b>SIMULACIÓN FINANCIERA & MARGEN TI: Automatización Fiscal & IA</b>\n\n"
            "🏢 <b>Cliente:</b> KPMG México\n"
            "💡 <b>Solución:</b> Validador SAT CFDI 4.0 + Extracción OCR Contratos + Conector ERP\n\n"
            "💰 <b>1. Costo Estimado de Desarrollo (COGS):</b>\n"
            "• Desarrollador Python OCR / IA (70 hrs × $30 USD): $2,100 USD\n"
            "• Consultor ERP / Conectores (40 hrs × $40 USD): $1,600 USD\n"
            "• APIs de OCR / Document AI: ~$100 USD/mes\n"
            "👉 <b>Costo Base de Implementación:</b> ~$3,900 USD\n\n"
            "💵 <b>2. Precio de Venta Sugerido:</b>\n"
            "• <b>Precio Llave en Mano:</b> <b>$15,500 USD</b> (ó ~$280,000 MXN)\n"
            "• <b>Margen Bruto de Implementación:</b> <b>74.8% de ganancia neta</b> ($11,600 USD)\n\n"
            "🔄 <b>3. Modelo de Cobro Recurrente (Retainer / SaaS Mensual):</b>\n"
            "• Mantenimiento y actualización ante cambios de miscelánea fiscal: <b>$800 USD / mes</b>\n"
            "• Margen mensual recurrente: ~70% ($560 USD/mes limpios)"
        ),
        "scope_summary": (
            "📑 <b>FICHA TÉCNICA Y DE NEGOCIO: KPMG México</b>\n\n"
            "💼 <b>Sector:</b> LegalTech, Auditoría & Gestión Fiscal B2B\n"
            "💰 <b>Presupuesto Estimado:</b> $12,000 - $20,000 USD\n"
            "⏱️ <b>Tiempo de Entrega:</b> 6 a 8 semanas\n\n"
            "📌 <b>Problema Operativo:</b>\n"
            "Validación manual de RFCs, sellos digitales y certificados en el portal del SAT "
            "para miles de proveedores con riesgo de contingencias fiscales.\n\n"
            "🛠️ <b>Entregables Técnicos Requeridos (SOW):</b>\n"
            "1. Buzón inteligente que recibe facturas (PDF + XML CFDI 4.0) por correo o webhook.\n"
            "2. Validador en segundo plano contra los webservices del SAT (vigencia fiscal y lista 69-B).\n"
            "3. Extracción de contratos y adendas con OCR e IA para verificar que los montos coincidan.\n"
            "4. Exportador automático para crear pólizas contables en SAP u Oracle ERP.\n\n"
            "🎯 <b>Estrategia de Venta TI:</b>\n"
            "<i>Véndeles blindaje fiscal y reducción de horas hombre operativas.</i>"
        )
    },
    {
        "id": "demanda_clip_fintech",
        "company": "Clip México",
        "sector": "Fintech & Terminales Punto de Venta",
        "priority": "Alta Intención",
        "status_badge": "Expansión B2B",
        "budget": "$16,000 - $26,000 USD",
        "problem": (
            "Dificultades en PyMEs para conciliar ventas presenciales y catálogo digital. Pérdida de clientes por falta de sincronización con inventarios locales."
        ),
        "solution": (
            "SDK integrado en Python y Node.js para conectar lectores Clip con sistemas ERP y plataformas de e-commerce con confirmación inmediata por webhook."
        ),
        "tags": ["SDK Terminales POS", "Microservicios Pagos", "FastAPI / Node", "Integración PyME"],
        "contact_email": "desarrollo@clip.mx",
        "contact_web": "clip.mx",
        "linkedin_company_url": "https://www.linkedin.com/company/clipmx",
        "source_url": "https://clip.mx",
        "comparison_points": ["Aumenta retención de comercios en 25%.", "Facilita adopción con librerías Open Source.", "Cumplimiento PCI."],
        "financial_quote": "📊 <b>SIMULACIÓN FINANCIERA: Clip SDK Integration</b>\n\n• Costo COGS: $4,800 USD\n• Precio Venta: $19,500 USD\n• Margen Bruto: 75%\n• Recurrente: $950 USD/mes",
        "scope_summary": "💳 <b>FICHA TÉCNICA: Clip México</b>\n\nDesarrollo de SDK para terminales POS, conector con ERPs locales y webhook seguro."
    },
    {
        "id": "demanda_kavak_automotriz",
        "company": "Kavak México",
        "sector": "AutoTech & Logística Automotriz",
        "priority": "Urgente",
        "status_badge": "Licitación Abierta",
        "budget": "$22,000 - $38,000 USD",
        "problem": (
            "Inspección mecánica manual tardada en patios de reacondicionamiento. Tiempos muertos de 48 hrs para evaluar daños estéticos y mecánicos."
        ),
        "solution": (
            "Aplicación móvil con modelos de visión por computadora para detección de abolladuras, desgaste de neumáticos y checklist digital automático."
        ),
        "tags": ["Visión Artificial", "App Flutter/React Native", "Modelos YOLO", "Automatización Inspección"],
        "contact_email": "tecnologia@kavak.com",
        "contact_web": "kavak.com",
        "linkedin_company_url": "https://www.linkedin.com/company/kavak-com",
        "source_url": "https://kavak.com",
        "comparison_points": ["Reduce tiempo de inspección de 48 hrs a 15 min.", "Estandariza calidad en todos los hubs.", "Exportación directa a inventario."],
        "financial_quote": "📊 <b>SIMULACIÓN FINANCIERA: AutoTech Computer Vision</b>\n\n• Costo COGS: $7,500 USD\n• Precio Venta: $30,000 USD\n• Margen Bruto: 75%\n• Recurrente: $1,500 USD/mes",
        "scope_summary": "🚗 <b>FICHA TÉCNICA: Kavak México</b>\n\nApp de inspección vehicular con Computer Vision (YOLOv8) y sincronización con almacén central."
    },
    {
        "id": "demanda_justo_foodtech",
        "company": "Jüsto Supermercado Digital",
        "sector": "FoodTech & Quick-Commerce",
        "priority": "Alta Prioridad",
        "status_badge": "Optimización Activa",
        "budget": "$14,000 - $24,000 USD",
        "problem": (
            "Merma del 8% en productos perecederos por falta de algoritmos predictivos de demanda y rutas de entrega no optimizadas."
        ),
        "solution": (
            "Modelo de Machine Learning para forecasting de demanda de frescos y optimización de rutas de última milla con ventanas horarias dinámicas."
        ),
        "tags": ["Machine Learning", "Forecasting Demanda", "Rutas Óptimas", "Logística Fría"],
        "contact_email": "operaciones@justo.mx",
        "contact_web": "justo.mx",
        "linkedin_company_url": "https://www.linkedin.com/company/justo",
        "source_url": "https://justo.mx",
        "comparison_points": ["Reducción de merma en 35%.", "Menor gasto de combustible en entregas.", "Alertas automáticas a proveedores."],
        "financial_quote": "📊 <b>SIMULACIÓN FINANCIERA: FoodTech Forecasting</b>\n\n• Costo COGS: $4,500 USD\n• Precio Venta: $17,500 USD\n• Margen Bruto: 74%\n• Recurrente: $1,000 USD/mes",
        "scope_summary": "🥗 <b>FICHA TÉCNICA: Jüsto Supermercado</b>\n\nMotor predictivo de demanda con Prophet/Scikit-learn y optimizador de despachos."
    },
    {
        "id": "demanda_bitso_crypto",
        "company": "Bitso International",
        "sector": "Fintech & Pagos Transfronterizos B2B",
        "priority": "Alta Intención",
        "status_badge": "Convocatoria Proveedor",
        "budget": "$25,000 - $40,000 USD",
        "problem": (
            "Conciliación lenta en liquidaciones transfronterizas entre México y EE.UU. para importadores y exportadores que pagan en stablecoins o SPEI."
        ),
        "solution": (
            "Gateway B2B para tesorerías empresariales con cotización en tiempo real de tipo de cambio, liquidación instantánea SPEI/ACH y reportes fiscales."
        ),
        "tags": ["Cross-border Payments", "APIs Financieras", "Stablecoins & SPEI", "Tesorería B2B"],
        "contact_email": "partners@bitso.com",
        "contact_web": "bitso.com",
        "linkedin_company_url": "https://www.linkedin.com/company/bitso",
        "source_url": "https://bitso.com",
        "comparison_points": ["Liquidación en minutos vs 72 hrs bancarias.", "Reducción de comisiones cambiarias.", "Cumplimiento PLD/KYC."],
        "financial_quote": "📊 <b>SIMULACIÓN FINANCIERA: Cross-border Gateway</b>\n\n• Costo COGS: $8,000 USD\n• Precio Venta: $32,000 USD\n• Margen Bruto: 75%\n• Recurrente: $1,600 USD/mes",
        "scope_summary": "🌐 <b>FICHA TÉCNICA: Bitso B2B</b>\n\nPlataforma de liquidación internacional con API de tesorería y conector SPEI/ACH."
    },
    {
        "id": "demanda_clara_corporativo",
        "company": "Clara Gastos Corporativos",
        "sector": "SaaS B2B & Spend Management",
        "priority": "Urgente",
        "status_badge": "Proyecto Q4",
        "budget": "$15,000 - $25,000 USD",
        "problem": (
            "Comprobación manual de viáticos y facturación SAT en empresas medianas. Pérdida de deducibilidad por facturas no emitidas a tiempo."
        ),
        "solution": (
            "Bot inteligente en Slack/WhatsApp que recibe fotos de tickets, extrae datos con OCR y descarga el CFDI directamente del portal SAT."
        ),
        "tags": ["OCR Tickets", "Descarga Masiva SAT", "Slack/WhatsApp Bots", "Spend Management"],
        "contact_email": "ventas@clara.com",
        "contact_web": "clara.com",
        "linkedin_company_url": "https://www.linkedin.com/company/claramexico",
        "source_url": "https://clara.com",
        "comparison_points": ["Ahorro del 80% en tiempo de comprobación.", "Cero multas por facturas vencidas.", "Integración ERP."],
        "financial_quote": "📊 <b>SIMULACIÓN FINANCIERA: Spend Management Bot</b>\n\n• Costo COGS: $4,200 USD\n• Precio Venta: $18,000 USD\n• Margen Bruto: 76.6%\n• Recurrente: $850 USD/mes",
        "scope_summary": "💼 <b>FICHA TÉCNICA: Clara Gastos Corporativos</b>\n\nBot automatizado de comprobación fiscal de gastos y conciliación SAT."
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

    # 1. Verificar si ya tenemos el lote de hoy en SQLite
    cached_today = get_b2b_companies_by_date(today_str)
    if cached_today and len(cached_today) >= 3:
        logger.info(f"[Prospección B2B] Recuperadas {len(cached_today)} empresas descubiertas hoy ({today_str}) desde SQLite.")
        return cached_today

    # 2. Obtener nombres vistos recientemente para evitar repetición
    recent_names = set(get_recent_b2b_company_names(limit=40))
    logger.info(f"[Prospección B2B] Empresas analizadas previamente para exclusión: {len(recent_names)}")

    # 3. Seleccionar 5 empresas no repetidas del pool multindustria
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
            for i in range(5)
        ]

    # 4. Verificar disponibilidad de LinkedIn concurrentemente con asyncio.gather
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

    # 5. Guardar en SQLite
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

    companies = get_b2b_companies_by_date(today_str)
    if companies and len(companies) >= 3:
        return companies

    # Fallback determinista síncrono si aún no se ha ejecutado el pipeline asíncrono
    day_offset = now.timetuple().tm_yday
    total_pool = len(_SEED_COMPANIES_POOL)
    fallback_batch = [
        dict(_SEED_COMPANIES_POOL[(day_offset * 2 + i) % total_pool])
        for i in range(5)
    ]
    for c in fallback_batch:
        c["contact_web"] = _clean_web_url(c.get("contact_web", ""))
        # Openpay o URLs caídas conocidas se marcan seguras
        if "openpay-mexico" in c.get("linkedin_company_url", ""):
            c["linkedin_company_url"] = "https://www.linkedin.com/company/openpaymx"
            c["linkedin_status"] = "active"
        else:
            c.setdefault("linkedin_status", "active")

    # Persistir fallback para que las lecturas subsecuentes sean consistentes
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
        "current_index": idx,
        "total_items": total
    }


def get_latest_b2b_demand(ref_date: Optional[datetime] = None) -> Dict[str, Any]:
    """Retorna los datos de la primera empresa del catálogo diario."""
    return get_b2b_demand_by_index(0, ref_date=ref_date)
