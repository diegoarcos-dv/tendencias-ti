# 📚 GUÍA DE ESTUDIO Y BITÁCORA TÉCNICA: ARQUITECTURA DEL AGENTE B2B & RADAR TI
> **Proyecto:** `tendencias-ti` | **Versión:** Producción v2.6  
> **Fecha de creación:** 15 de Octubre de 2026  
> **Propósito:** Documento vivo para el estudio, preparación de presentaciones y auditoría de la arquitectura del agente inteligente.

---

## 🗺️ MAPA GENERAL DE LA ARQUITECTURA (6 FASES)

```mermaid
flowchart LR
    F1["Fase 1: Ingesta & Fuentes"] --> F2["Fase 2: Motor IA & Scoring"]
    F2 --> F3["Fase 3: Persistencia SQLite WAL"]
    F3 --> F4["Fase 4: Motor Visual Playwright"]
    F4 --> F5["Fase 5: Telegram & Rama B"]
    F5 --> F6["Fase 6: Seguridad & Blindaje"]
```

1. **Fase 1: Ingesta de Información y Fuentes de Entrada:** Captura y normalización de tendencias, eventos y licitaciones.
2. **Fase 2: Motor de Inteligencia, Deduplicación y Scoring:** Evaluación de tracción, hashing SHA-256 y priorización algorítmica.
3. **Fase 3: Memoria Persistente y Gestión del Estado:** SQLite en modo WAL, tablas relacionales y auto-purga.
4. **Fase 4: Motor Visual Headless & Generación de Artefactos:** Playwright renderizando tarjetas 1080x1080px a 60fps.
5. **Fase 5: Orquestación de Salida & Rama B (Funnels):** Bot de Telegram interactivo y simulación financiera privada (SOW).
6. **Fase 6: Seguridad y Blindaje Perimetral:** DLP, HMAC en tiempo constante, anti-prompt injection y whitelist HTML.

---

## ❓ SESIÓN 1: PREGUNTAS Y RETROALIMENTACIÓN DE FASE 1 (INGESTA)

---

### 📌 Pregunta 1: ¿Cómo se desglosa y qué significa cada parte de la infografía generada por el agente?

#### 💡 Retroalimentación & Explicación Técnica:
La infografía generada por Playwright (`tarjeta_demanda_b2b.html`) sintetiza una oportunidad de negocio en una sola imagen de alta resolución:

```
+------------------------------------------------------------------------+
| 🏛️ GOBIERNO / CORPORATIVO (Ej. FGJCDMX)                 [Licitación]   | <- [1] Header de Identidad
+------------------------------------------------------------------------+
|  OPORTUNIDAD DETECTADA: SERVICIOS DE DESARROLLO DE SOFTWARE & IA       | <- [2] Título del Requerimiento
|  Expediente Oficial: LPN/FGJCDMX/DACS-060/2025                         |
+------------------------------------------------------------------------+
|  📅 Apertura: 15 Oct 2026      |  💰 Presupuesto Estimado: $4.8M MXN   | <- [3] Metadatos Clave
|  📍 Entidad: CDMX Digital      |  🎯 Compatibilidad: 94% Alta          |
+------------------------------------------------------------------------+
|  REQUERIMIENTOS TÉCNICOS ESENCIALES:                                   | <- [4] Stack Requerido
|  • Python / FastAPI / Microservicios                                   |
|  • PostgreSQL con Alta Disponibilidad                                  |
|  • Cumplimiento con Ley de Adquisiciones CDMX                          |
+------------------------------------------------------------------------+
|  🤖 Justificación de la IA: "Se requiere fábrica de software para      | <- [5] Análisis de Tracción
|     modernización de plataformas de atención ciudadana y trámites."   |
+------------------------------------------------------------------------+
|  [ 🌐 Ver más ↗️ ]               [ 💼 Cotizar Solución Privada ↗️ ]     | <- [6] Botonera (Acciones)
+------------------------------------------------------------------------+
```

1. **Header de Identidad y Badge:** Indica la entidad convocante y si es una licitación pública o un requerimiento empresarial privado.
2. **Título del Requerimiento y Expediente Oficial:** Código auditable (ej. `LPN/FGJCDMX/DACS-060/2025`) para sustentar la veracidad legal.
3. **Grid de Metadatos Clave:** Fechas límites de presentación, techos presupuestales y el índice de compatibilidad técnica con los servicios del integrador.
4. **Requerimientos Técnicos Esenciales:** Las tecnologías, certificaciones (ISO 27001, CSSLP) y perfiles exigidos por las bases.
5. **Justificación Ejecutiva del Motor de IA:** Resumen claro generado por la IA que explica por qué surge esta necesidad en la organización.
6. **Botonera de Acción:**
   * Botón primario (`[ 🌐 Ver más ↗️ ]`): Abre el portal oficial donde está publicado el pliego técnico.
   * Botón secundario (`[ 💼 Cotizar Solución Privada ↗️ ]`): Abre el deep-link cifrado a Telegram con la cotización financiera y margen bruto de ganancia (Rama B).

---

### 📌 Pregunta 2: ¿En qué se basa el filtrado estricto en la demanda B2B? ¿Cuáles son las fuentes y por qué son seguras?

#### 💡 Retroalimentación & Explicación Técnica:
El filtrado estricto resolvió el problema de enlaces genéricos o irrelevantes (como portales de supermercados vendiendo abarrotes).

#### A. Criterios de Filtrado Obligatorios:
1. **Evidencia Documental Directa:** Exige expediente auditable y URL pública directa al pliego de requisitos técnicos (TDR).
2. **Corte Temático de TI:** Se rechazan compras de suministros, alimentos o mobiliario. Solo se aceptan licitaciones de: *Fábricas de software, microservicios, infraestructura cloud, bases de datos y ciberseguridad*.
3. **Cero Muros de Registro Forzoso:** Se eliminaron enlaces de LinkedIn o plataformas con inicio de sesión obligatorio (`linkedin.com/login`).
4. **Protección TDD (`test_b2b_procurement_tdd.py`):** Existe una lista negra automatizada (`OBSOLETE_ENTITIES`). Si una entidad sin sustento intenta entrar, la suite de pruebas detiene el despliegue.

#### B. Fuentes y Seguridad Institucional:
* **Concurso Digital CDMX** (`concursodigital.finanzas.cdmx.gob.mx`): Subdominio gubernamental oficial de la Secretaría de Administración y Finanzas de la CDMX.
* **Tianguis Digital CDMX** (`tianguisdigital.finanzas.cdmx.gob.mx`): Plataforma oficial de contrataciones abiertas de la CDMX bajo el estándar internacional OCDS.
* **Seguridad:** Portales protegidos por certificados SSL/TLS emitidos para el Gobierno de la CDMX (`.gob.mx`), información pública y libre de malware o rastreadores comerciales.

---

### 📌 Pregunta 3: ¿Cuáles son las fuentes de tendencias tecnológicas y eventos en CDMX? (La totalidad de la Fase 1)

#### 💡 Retroalimentación & Explicación Técnica:
La Fase 1 se conforma por **3 pilares paralelos**:

| Pilar | Fuentes Principales | Archivos Responsables | Tipo de Información |
| :--- | :--- | :--- | :--- |
| **Pilar A: Tendencias Globales** | Product Hunt, Reddit B2B, Google Trends, TechCrunch Enterprise, Hacker News (Y Combinator) | `app/connectors.py`<br>`app/context_reader.py` | Tecnologías nacientes, tracción social, dolores de mercado y software SaaS. |
| **Pilar B: Eventos TI CDMX** | Portales de NVIDIA, Microsoft, AWS, IBM, Google Cloud + Entrada manual Telegram (`/nuevo_evento`) | `app/events_cdmx.py`<br>`app/database.py` | Cumbres presenciales, congresos de IA y networking para directores de tecnología. |
| **Pilar C: Demanda B2B** | Concurso Digital CDMX, Tianguis Digital | `app/b2b_demand.py` | Contratos públicos y licitaciones de software con presupuesto asignado. |

---

### 📌 Pregunta 4: ¿Cómo sabe el agente que en Reddit no son personas comentando cosas al azar? ¿Cómo funciona el filtrado del Pilar A?

#### 💡 Retroalimentación & Explicación Técnica:
Para que un post de Reddit llegue al agente, debe superar **5 filtros matemáticos y temáticos**:

1. **Aislamiento por Subreddits Profesionales:** No se consulta la portada de Reddit (`r/all` está bloqueado). Se leen exclusivamente comunidades de ingeniería y negocios (`r/SaaS`, `r/technology`, `r/cybersecurity`, `r/devops`, `r/cloud`, `r/artificial`).
2. **Enrutamiento por Industria (`INDUSTRY_SUBREDDIT_MAP`):** Si se consulta Fintech, el agente solo va a `r/Fintech`, `r/CryptoCurrency` y `r/banking`.
3. **Filtro de Tracción Algorítmica (`/hot.json` + `score`):** Descarta comentarios sueltos o posts con 0 upvotes. Solo pasan publicaciones que la comunidad votó y validó masivamente.
4. **Descarte de Anuncios y Spoilers (`stickied: true`):** No se procesa publicidad ni avisos fijados de moderadores.
5. **Filtro de Caducidad (`MAX_TREND_AGE_HOURS`):** Publicaciones con más de 24-48 horas se descartan automáticamente.
6. **Fallback de Respaldo B2B:** Si Reddit se cae o es bloqueado por rate limits, el conector consulta la API de **Hacker News (Y Combinator)** y el feed de **TechCrunch Enterprise**.

---

### 📌 Pregunta 5: ¿Quién hace esas reglas estrictas? ¿El mismo agente? ¿Eso no es garantía de que la información sea verídica o cómo funciona esto?

#### 💡 Retroalimentación & Explicación Técnica:

#### 1. ¿Quién define las reglas?
* **NO las define el agente:** El modelo de lenguaje (LLM) no tiene autorización para inventar reglas ni decidir a qué URLs conectarse.
* **Las define el código duro de Python:** En [`app/connectors.py`](file:///c:/Users/victor%20adan/Documents/TENDENCIAS-TI/app/connectors.py) están escritas las listas negras, los endpoints permitidos y los tipos de datos en Pydantic.
* **Arquitectura de Confinamiento:** El código actúa como la aduana; la IA solo recibe datos que ya fueron desinfectados y aprobados previamente.

#### 2. La gran distinción: Verdad Legal vs. Detección de Dolores de Mercado
El sistema divide la información en dos propósitos claramente delimitados:

* **Mundo 1: Certeza Contractual y Legal 100% (Pilares B y C):**  
  * *Fuentes:* Concurso Digital CDMX, Tianguis Digital, eventos oficiales de NVIDIA/Microsoft.
  * *Garantía:* Documentos de compras gubernamentales con números de expediente oficiales amparados por leyes de contratación.
* **Mundo 2: Sensor de Tracción y Oportunidades de Mercado (Pilar A):**  
  * *Fuentes:* Reddit B2B, Product Hunt, Hacker News.
  * *Garantía:* No se busca un contrato firmado, sino responder: *¿Qué dolores técnicos tienen los ingenieros?, ¿qué herramientas están en auge?, ¿qué problemas de infraestructura están reportando los usuarios?*

#### 3. ¿Cómo se evita que un usuario mentiroso engañe al agente?
1. **Consenso Colectivo:** Un post aislado sin votos nunca llega al feed `/hot.json`.
2. **Cruce contra la "Fuente de Verdad" (`data/tendencias.txt`):** El código coteja si el tema aborda las 3 líneas estratégicas (E-commerce B2B, IA & Analítica, Infraestructura TI). Si no encaja, el código lo purga con `.evaluate_relevance()`.
3. **Triangulación con Periodismo Tech:** Conexión de respaldo con Y Combinator y TechCrunch Enterprise.

---

### 📌 Pregunta 6: ¿Cuáles son las medidas de ciberseguridad implementadas en todo el flujo de ingesta?

#### 💡 Retroalimentación & Explicación Técnica:
En [`app/security.py`](file:///c:/Users/victor%20adan/Documents/TENDENCIAS-TI/app/security.py) operan 4 barreras de defensa en profundidad:

1. **Defensa contra Indirect Prompt Injection (`sanitize_external_text`):**  
   Analiza textos externos con expresiones regulares para detectar ataques de secuestro (*"ignore all previous instructions"*, *"system prompt"*, *"reveal secret"*). Si detecta un patrón malicioso, lo sustituye por `[CONTENIDO RESTRINGIDO POR SEGURIDAD]`.
2. **Prevención de Fuga de Datos (DLP - Data Leak Prevention) (`redact_sensitive_data`):**  
   Monitorea todos los mensajes salientes. Si detecta tokens de Telegram, direcciones IP privadas (`10.108.18.4`, `192.168.x.x`) o rutas del sistema de archivos (`/apps/tendencias-ti`), los ofusca automáticamente.
3. **Autenticación con HMAC en Tiempo Constante (`verify_api_key`):**  
   Usa `hmac.compare_digest()` para evitar ataques de temporización (timing attacks) que intenten adivinar claves de acceso midiendo tiempos de respuesta en nanosegundos.
4. **Validación Estricta de Esquemas con Pydantic (`TrendItem`):**  
   Cero tipado dinámico inseguro; todo dato crudo que entra por la red es forzado a un esquema estricto antes de almacenarse en la base de datos SQLite.

---

### 📌 Pregunta 7: ¿Cómo respaldar que Product Hunt, Reddit B2B y Google Trends son fuentes confiables y tienen información real?

#### 💡 Retroalimentación & Explicación Técnica:

#### A. Respaldo Institucional y Operativo:
1. **Product Hunt (Propiedad de AngelList):** Es el estándar de facto mundial para lanzamientos de startups y software SaaS. No son rumores: son los propios fundadores e ingenieros de software quienes registran sus empresas (como lo hicieron OpenAI, Notion o Stripe en sus inicios) con dominio oficial, precios y demostraciones auditables.
2. **Google Trends:** Es telemetría directa y estadística de Google. Refleja el volumen real agregado de millones de búsquedas corporativas y ciudadanas en México y el mundo, libre de opiniones sesgadas.
3. **Reddit B2B (Comunidades Técnicas Especializadas):** Es el mayor repositorio de "casos de uso en el mundo real" y dolores de producción. Ingenieros DevOps y directores de TI reportan fallos reales, costos ocultos de nube y cuellos de botella que los proveedores de software no publican en sus folletos de marketing.

#### B. Mecanismos de Verificación en Código (`app/connectors.py`):
1. **Resolución al Dominio Oficial del Creador (`extract_creator_external_url`):** Resuelve redirecciones HTTP (301/302) para extraer la web raíz de la empresa, evitando intermediarios.
2. **Auditoría Obligatoria (`audit_url` y `verified_source`):** Todo objeto `TrendItem` almacena el enlace canónico donde un evaluador humano puede contrastar el origen del dato.
3. **APIs Oficiales y Esquemas Tipados:** Uso de GraphQL v2 en Product Hunt, RSS geolocalizado en Google Trends (`geo=MX`) y la API oficial de Firebase de Y Combinator (Hacker News).

#### C. Filtro Semántico contra la Fuente de Verdad (`data/tendencias.txt`):
Aunque una tendencia sea viral, si no resuelve una necesidad de las 3 líneas estratégicas (E-commerce B2B, IA & Analítica, Infraestructura de Software), la función `.evaluate_relevance()` la descarta del flujo.

---

### 📌 Pregunta 8: ¿En qué está basada la "Fuente de Verdad"? ¿Aplica para cualquier industria? ¿Qué pasa si busco tendencias de ganadería?

#### 💡 Retroalimentación & Explicación Técnica:

#### A. Origen y Definición de la Fuente de Verdad:
El archivo `data/tendencias.txt` nació enfocado en el giro del proyecto (`tendencias-ti`): una firma o fábrica de desarrollo de software y servicios cloud. Por ello, prioriza los 3 nichos con mayor margen comercial en México:
1. *E-Commerce B2B y Pasarelas.*
2. *Inteligencia Artificial & Analítica Empresarial.*
3. *Infraestructura TI, Microservicios y Ciberseguridad.*

#### B. El Caso de la "Ganadería" (¿Pasa o no el filtro?):
La función `is_relevant_to_business()` en `app/context_reader.py` evalúa el componente tecnológico:
* **Ganadería Tradicional (Rechazada ❌):** Si la noticia trata sobre precios de forraje, clima para el pastoreo o venta de reses en pie, el sistema la descarta porque carece de componente de software o sistemas.
* **Ganadería Inteligente / AgriTech (Aprobada ✅):** Si la tendencia trata sobre *"Collares IoT para monitoreo bovino conectado a la nube"* o *"Software SaaS para trazabilidad de ganado y trazabilidad con visión por computadora"*, **sí pasa el filtro**, ya que activa palabras clave de arquitectura (`IoT`, `SaaS`, `Cloud`, `Analytics`, `IA`).

#### C. Arquitectura Desacoplada (Adaptable a Cualquier Industria):
El sistema no tiene las reglas de negocio "quemadas" (hardcoded) en el código.  
Para transformar el bot a cualquier otra industria (Agropecuario, Minería, Bienes Raíces o Salud), basta con editar `data/tendencias.txt` y agregar las nuevas líneas estratégicas (ej. `## 4. AgriTech y Ganadería Digital`). La clase `BusinessContextReader` recarga dinámicamente el vocabulario en memoria sin tener que modificar una sola línea del código fuente ni compilar de nuevo.

---

### 📌 Pregunta 9: En la Rama B, cuando personalizo alertas y elijo una industria (ej. Ganadería), ¿cómo selecciona la tendencia y la adapta a una solución con TI?

#### 💡 Retroalimentación & Explicación Técnica:

```mermaid
flowchart TD
    A["1. Usuario en Telegram elige: 'Ganadería'"] --> B["2. Inyección de Puente TI: 'tecnología ganaderia' / 'ganaderia B2B'"]
    B --> C["3. Scoring Engine aplica Bono de Afinidad (+3,000 pts)"]
    C --> D["4. LLM actúa como Arquitecto de Solución Tecnológica"]
    D --> E["5. Genera Tarjeta Visual + Cotización SOW de Software (Rama B)"]
```

#### 1. Inyección del "Puente Tecnológico" en la Búsqueda (`app/connectors.py`):
El conector no busca la industria de forma aislada para evitar traer noticias agropecuarias puras. La función `get_keywords_for_industry(industry="ganadería")` genera consultas híbridas:
```python
# app/connectors.py línea 475
kws = [
    "ganaderia",
    "ganaderia B2B",
    "tecnología ganaderia"   # <--- Inyección del puente hacia TI
]
```
Esto fuerza a Google Trends, Product Hunt y Reddit a buscar innovaciones donde el sector ya se cruza con software e ingeniería (ej. collares RFID, telemetría IoT, software de gestión de hatos).

#### 2. Priorización Ponderada en el Scoring (`app/main.py`):
Al clasificar las tendencias del día, la función `calculate_tool_score()` detecta la industria del usuario:
```python
# app/main.py línea 140
industry_bonus = 0.0
if industry and industry.lower() not in ("global", "ti & software b2b"):
    ind_words = [w.lower() for w in industry.split() if len(w) > 3]
    if any(w in item_text for w in ind_words):
        industry_bonus = 3000.0  # <--- Bono masivo de afinidad
```
La tendencia de ganadería recibe **+3,000 puntos directos** más **+2,500 puntos** si es producto de software, superando a tendencias genéricas y quedando como la **número 1**.

#### 3. Validación de Pertinencia con TI (`app/context_reader.py`):
La tendencia candidata contiene palabras como `SaaS`, `IoT`, `Sensores` o `Cloud`. Esto permite que `is_relevant_to_business()` la marque como relevante (`business_relevant = True`), evitando la penalización de descarte.

#### 4. Traducción a Arquitectura de Software por el LLM (`app/llm_service.py`):
El LLM asume el rol de **Arquitecto de Soluciones Tecnológicas B2B**:
* **Dolor de la Industria:** Control de inventario de ganado, abigeato y trazabilidad sanitaria.
* **Adopción con TI generada:**
  * `problem_solved`: Automatización de pesaje y trazabilidad en ranchos.
  * `stack_sugerido`: `["Sensores IoT / MQTT", "Python / FastAPI", "PostgreSQL", "Dashboard React"]`.
  * `target_industry`: Ranchos ganaderos y asociaciones de engorda.
  * `summary`: Resumen ejecutivo enfocado en eficiencia operativa y ROI.

#### 5. Cierre Comercial en la Rama B (`app/rama_b.py`):
Al presionar `[ 💼 Simular Cotización ]`, el bot entrega el **Statement of Work (SOW)** financiero:
* Costo de Célula (Tech Lead IoT + Devs Backend): ~$7,700 USD.
* Precio de Oferta al Ganadero: $14,500 USD.
* **Margen Neto de Ganancia:** **46.8% de ganancia limpia** para la empresa de TI.

---

### 📌 Pregunta 10: Con la migración de Gemma a LLaMA 3.1, ¿se utilizaron archivos `.md`? ¿Para qué? ¿Cuál es su función?

#### 💡 Retroalimentación & Explicación Técnica:

**SÍ.** En la arquitectura de prompts modular (estándar **SoulSpec**) se estructuraron 4 archivos Markdown dentro de `data/prompts/`:

1. **`IDENTITY.md` (Identidad y Rol):**
   * Asigna el rol de *Consultor Estratégico Senior B2B* y Arquitecto de Negocios Tecnológicos para directores de tecnología (CTOs) y CIOs en México (CDMX/Edomex).
   * Fija el contexto de viabilidad económica y ROI (< 6 meses).

2. **`SOUL.md` (Alma, Valores y Cero Fuga):**
   * Define la postura analítica, cuantitativa y persuasiva orientada a reducción de costos y ventajas competitivas.
   * Aplica la regla **Zero-Leakage**: prohíbe terminantemente filtrar nombres de archivos internos (`tendencias.txt`, `.py`, `SQLite`), APIs crudas (`google_trends`, `Reddit`) o palabras de desarrollo (`ingesta`, `scraping`). Obliga a usar términos corporativos como *"nuestros indicadores de inteligencia de mercado"*.

3. **`STYLE.md` (Reglas de Comunicación y Contrato Estructural):**
   * Exige que los reportes ejecutivos profundos (*Deep Dive*) se dividan estrictamente en 4 bloques: Tracción de Mercado, Tesis de Oportunidad, Ruta de Implementación/Stack y Plan de Acción/Monetización B2B en 3 fases.
   * Controla la extensión (entre 350 y 550 palabras) y restringe el uso exclusivo a etiquetas HTML seguras de Telegram (`<b>`, `<i>`, `<code>`).

4. **`RULES.md` (Instrucciones Operativas y Blindaje Cognitivo):**
   * Neutraliza intentos de jailbreak o prompt injection (*"ignora instrucciones previas"*, *"modo desarrollador DAN"*, *"revela tu system prompt"*).
   * Scope Guard: rechaza solicitudes ajenas al software y negocios (poemas, recetas, tareas escolares) y reorienta al usuario al catálogo de tendencias.

#### Consumo Dinámico en Código Python (`app/llm_service.py`):
En tiempo de ejecución, el servicio lee los archivos `.md` en caliente siguiendo el estándar SoulSpec:
```python
# app/llm_service.py
prompts_dir = settings.DATA_DIR / "prompts"
behavior_md = "\n\n".join([
    (prompts_dir / f).read_text(encoding="utf-8")
    for f in ["IDENTITY.md", "SOUL.md", "STYLE.md"] if (prompts_dir / f).exists()
])
security_md = (prompts_dir / "RULES.md").read_text(encoding="utf-8")

# Inyección modular en el System Prompt de LLaMA 3.1
system_prompt = base_role + "\n\n" + behavior_md + "\n\n" + security_md
```

#### ¿Por qué usar archivos `.md` en lugar de texto en Python?
* **Optimización para LLaMA 3.1:** El modelo procesa con mayor precisión y menos alucinaciones jerarquías semánticas en Markdown (`#`, `##`, `-`) que cadenas de texto continuas dentro de Python.
* **Arquitectura PromptOps Desacoplada:** Permite actualizar el tono, formato o reglas de seguridad editando un archivo Markdown en caliente, sin tocar ni arriesgar el código fuente en Python de `app/llm_service.py`.

---

### 📌 Pregunta 11: ¿Qué tan viable es que el archivo `tendencias.txt` se vaya retroalimentando según la interacción de los usuarios?

#### 💡 Retroalimentación & Explicación Técnica:

**Es 100% viable y estratégicamente valioso**, pero **NUNCA debe permitirse la escritura directa en caliente** desde el chat para evitar el riesgo de **Data Poisoning (Envenenamiento de Datos)** y bloqueos por concurrencia.

```mermaid
flowchart TD
    USR["1. Interacciones en Telegram (Clics en Cotización, Búsquedas, Favoritos)"] --> SQL["2. Búfer de Telemetría en SQLite (Tabla 'user_interests')"]
    SQL --> CRON["3. Analizador de Frecuencia (Job Nocturno)"]
    CRON --> COND{"¿Superó el umbral? (Ej. >15 usuarios distintos)"}
    COND -- No --> IGN["Descarta / Mantiene en espera"]
    COND -- Sí --> ADMIN{"4. Validación de Integridad (Supervisor o LLM Guardrail)"}
    ADMIN --> TXT["5. Se anexa la nueva Línea Estratégica en tendencias.txt"]
```

#### A. Los Riesgos de una Escritura Directa:
1. **Data Poisoning:** Si un atacante o usuario escribe temas ajenos (fútbol, farándula, política) y se agregan a `tendencias.txt`, el bot contaminaría su radar y empezaría a enviar notas irrelevantes a clientes corporativos.
2. **Race Conditions:** Múltiples usuarios escribiendo concurrentemente en un archivo de texto plano pueden corromper el contenido o provocar errores de I/O en el servidor.

#### B. La Arquitectura Segura en 3 Capas:
1. **Capa 1 - Búfer de Telemetría en SQLite:** Las búsquedas, selecciones de industria y clics en `[ Simular Cotización ]` se guardan como métricas de comportamiento en una tabla SQLite de eventos, sin tocar el archivo `.txt`.
2. **Capa 2 - Filtro Estadístico de Tracción:** Un job periódico evalúa la frecuencia: solo si una industria (ej. *Ganadería / IoT*) es consultada por $N$ usuarios distintos (ej. más de 15), se califica como "Oportunidad de Mercado Validada".
3. **Capa 3 - Validación Human-in-the-Loop o Guardrail IA:**
   * **Modo Supervisado (Recomendado):** El bot envía una alerta al Administrador por Telegram: *"18 usuarios han consultado 'Ganadería Inteligente'. ¿Deseas incorporarla como Línea 4 en tendencias.txt? [Aprobar] [Rechazar]"*.
   * Al aprobar, el sistema inyecta la nueva categoría de forma atómica y `BusinessContextReader.load_context()` la asimila en memoria sin reiniciar el servidor.

#### C. Impacto en Negocio:
Transforma al agente de un catálogo estático a un **radar adaptativo de inteligencia de mercado**, aprendiendo de la demanda real de los usuarios en tiempo real.

---

*(Continuará con las siguientes fases conforme avancemos en el estudio)*
