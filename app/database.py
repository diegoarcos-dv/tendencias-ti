"""Capa de Orquestación y Memoria: Persistencia en SQLite para Bob.

Responsabilidades:
- Inicializar la base de datos y tablas de tendencias con migraciones automáticas.
- Normalizar URLs y títulos para deduplicación robusta con ventana de enfriamiento (cooldown).
- Evitar duplicados por URL o hash de contenido.
- Registrar tendencias procesadas, análisis estructurado de IA y favoritas.
- Almacenar el histórico de scores del Scoring Engine.
"""

import sqlite3
import hashlib
import json
import re
from typing import Optional, List, Dict, Any, Union
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlunparse

from app.config import settings

# Ruta canónica del archivo de base de datos
DB_PATH: Path = settings.DATA_DIR / "radar.db"


def _get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Retorna una conexión SQLite con row_factory configurada."""
    path = str(db_path or DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Inicializa la base de datos SQLite, crea las tablas y aplica migraciones si no existen."""
    resolved = Path(db_path) if db_path else DB_PATH
    resolved.parent.mkdir(parents=True, exist_ok=True)

    with _get_connection(resolved) as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS historial_envios (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                url               TEXT    NOT NULL,
                url_hash          TEXT    NOT NULL UNIQUE,
                title             TEXT    NOT NULL,
                source            TEXT    NOT NULL DEFAULT '',
                category          TEXT    NOT NULL DEFAULT '',
                score             REAL    NOT NULL DEFAULT 0.0,
                sent_at           TEXT    NOT NULL,
                card_data         TEXT    DEFAULT NULL,
                normalized_title  TEXT    DEFAULT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_historial_url_hash
                ON historial_envios (url_hash);

            CREATE INDEX IF NOT EXISTS idx_historial_sent_at
                ON historial_envios (sent_at);

            CREATE TABLE IF NOT EXISTS tendencias_guardadas (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                url            TEXT    NOT NULL,
                url_hash       TEXT    NOT NULL,
                title          TEXT    NOT NULL,
                source         TEXT    NOT NULL DEFAULT '',
                category       TEXT    NOT NULL DEFAULT '',
                score          REAL    NOT NULL DEFAULT 0.0,
                llm_analysis   TEXT    DEFAULT NULL,
                saved_at       TEXT    NOT NULL,
                is_favorite    INTEGER NOT NULL DEFAULT 1,
                message_id     INTEGER DEFAULT NULL,
                UNIQUE(user_id, url_hash)
            );

            CREATE TABLE IF NOT EXISTS configuracion_usuario (
                chat_id            TEXT PRIMARY KEY,
                zona_preferida     TEXT NOT NULL DEFAULT 'Global',
                zona_local         TEXT NOT NULL DEFAULT '',
                zona_pais          TEXT NOT NULL DEFAULT '',
                zonas_json         TEXT NOT NULL DEFAULT '[]',
                industria          TEXT NOT NULL DEFAULT 'TI & Software B2B',
                industria_exacta   TEXT NOT NULL DEFAULT '',
                categoria_api      TEXT NOT NULL DEFAULT 'general',
                schedule_time      TEXT NOT NULL DEFAULT '10:00',
                freelance_role     TEXT NOT NULL DEFAULT '',
                freelance_skills   TEXT NOT NULL DEFAULT '[]',
                freelance_keywords TEXT NOT NULL DEFAULT '',
                onboarding_step    TEXT NOT NULL DEFAULT '',
                updated_at         TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS registro_tarjetas_enviadas (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id     TEXT    NOT NULL,
                message_id  INTEGER NOT NULL,
                chat_type   TEXT    NOT NULL DEFAULT 'private',
                created_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_tarjetas_created_at
                ON registro_tarjetas_enviadas (created_at);

            CREATE INDEX IF NOT EXISTS idx_tarjetas_chat_daily
                ON registro_tarjetas_enviadas (chat_id, created_at);

            CREATE TABLE IF NOT EXISTS b2b_empresas_demandantes (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id             TEXT    NOT NULL UNIQUE,
                company_name           TEXT    NOT NULL,
                sector                 TEXT    NOT NULL,
                priority               TEXT    NOT NULL,
                status_badge           TEXT    NOT NULL,
                budget                 TEXT    NOT NULL,
                problem                TEXT    NOT NULL,
                solution               TEXT    NOT NULL,
                tags_json              TEXT    NOT NULL DEFAULT '[]',
                contact_email          TEXT    NOT NULL DEFAULT '',
                contact_web            TEXT    NOT NULL DEFAULT '',
                linkedin_url           TEXT    NOT NULL DEFAULT '',
                linkedin_status        TEXT    NOT NULL DEFAULT 'active',
                source_url             TEXT    NOT NULL DEFAULT '',
                financial_quote        TEXT    NOT NULL DEFAULT '',
                scope_summary          TEXT    NOT NULL DEFAULT '',
                comparison_points_json TEXT    NOT NULL DEFAULT '[]',
                discovered_date        TEXT    NOT NULL,
                created_at             TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_b2b_discovered_date
                ON b2b_empresas_demandantes (discovered_date);

            CREATE TABLE IF NOT EXISTS eventos_empresariales (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id         TEXT    NOT NULL UNIQUE,
                org              TEXT    NOT NULL,
                access_label     TEXT    NOT NULL DEFAULT 'Registro Empresarial',
                title            TEXT    NOT NULL,
                fixed_date_str   TEXT    NOT NULL DEFAULT '',
                days_ahead       INTEGER NOT NULL DEFAULT 15,
                hour_str         TEXT    NOT NULL DEFAULT '09:00 hrs a 18:00 hrs',
                venue            TEXT    NOT NULL,
                target_audience  TEXT    NOT NULL DEFAULT '',
                requirements     TEXT    NOT NULL DEFAULT '',
                tags_json        TEXT    NOT NULL DEFAULT '[]',
                platform_name    TEXT    NOT NULL DEFAULT 'Portal Oficial',
                platform_domain  TEXT    NOT NULL DEFAULT '',
                platform_mode    TEXT    NOT NULL DEFAULT 'Presencial · Sede Corporativa',
                registration_url TEXT    NOT NULL DEFAULT '',
                info_summary     TEXT    NOT NULL DEFAULT '',
                created_at       TEXT    NOT NULL,
                is_active        INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_eventos_is_active
                ON eventos_empresariales (is_active, id DESC);

            CREATE TABLE IF NOT EXISTS telemetria_interacciones (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                chat_id     TEXT    NOT NULL,
                action_type TEXT    NOT NULL,
                industry    TEXT    NOT NULL DEFAULT '',
                details     TEXT    DEFAULT '',
                created_at  TEXT    NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_telemetria_action_ind
                ON telemetria_interacciones (action_type, industry);

            CREATE INDEX IF NOT EXISTS idx_telemetria_created_at
                ON telemetria_interacciones (created_at);
        """)

        # Migración ligera: asegurar columnas nuevas si la tabla ya existía previamente
        existing_cols = {
            col[1]
            for col in conn.execute("PRAGMA table_info(historial_envios)").fetchall()
        }
        if "card_data" not in existing_cols:
            conn.execute("ALTER TABLE historial_envios ADD COLUMN card_data TEXT DEFAULT NULL")
        if "normalized_title" not in existing_cols:
            conn.execute("ALTER TABLE historial_envios ADD COLUMN normalized_title TEXT DEFAULT NULL")

        guardadas_cols = {
            col[1]
            for col in conn.execute("PRAGMA table_info(tendencias_guardadas)").fetchall()
        }
        if "message_id" not in guardadas_cols:
            conn.execute("ALTER TABLE tendencias_guardadas ADD COLUMN message_id INTEGER DEFAULT NULL")
        if "user_id" not in guardadas_cols:
            conn.execute("ALTER TABLE tendencias_guardadas ADD COLUMN user_id TEXT DEFAULT NULL")

        cfg_cols = {
            col[1]
            for col in conn.execute("PRAGMA table_info(configuracion_usuario)").fetchall()
        }
        if "zona_preferida" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN zona_preferida TEXT NOT NULL DEFAULT 'Global'")
        if "zona_local" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN zona_local TEXT NOT NULL DEFAULT ''")
        if "zona_pais" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN zona_pais TEXT NOT NULL DEFAULT ''")
        if "zonas_json" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN zonas_json TEXT NOT NULL DEFAULT '[]'")
        if "industria" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN industria TEXT NOT NULL DEFAULT 'TI & Software B2B'")
        if "industria_exacta" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN industria_exacta TEXT DEFAULT ''")
        if "categoria_api" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN categoria_api TEXT DEFAULT 'general'")
        if "schedule_time" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN schedule_time TEXT NOT NULL DEFAULT '10:00'")
        if "freelance_role" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN freelance_role TEXT NOT NULL DEFAULT ''")
        if "freelance_skills" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN freelance_skills TEXT NOT NULL DEFAULT '[]'")
        if "freelance_keywords" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN freelance_keywords TEXT NOT NULL DEFAULT ''")
        if "onboarding_step" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN onboarding_step TEXT NOT NULL DEFAULT ''")

        b2b_cols = {
            col[1]
            for col in conn.execute("PRAGMA table_info(b2b_empresas_demandantes)").fetchall()
        }
        if "demand_source_type" not in b2b_cols and b2b_cols:
            conn.execute("ALTER TABLE b2b_empresas_demandantes ADD COLUMN demand_source_type TEXT DEFAULT ''")
        if "demand_source_label" not in b2b_cols and b2b_cols:
            conn.execute("ALTER TABLE b2b_empresas_demandantes ADD COLUMN demand_source_label TEXT DEFAULT ''")
        if "demand_evidence_url" not in b2b_cols and b2b_cols:
            conn.execute("ALTER TABLE b2b_empresas_demandantes ADD COLUMN demand_evidence_url TEXT DEFAULT ''")


def _normalize_url(url: str) -> str:
    """Normaliza una URL eliminando fragmentos, trailing slashes y parámetros de rastreo (UTM, ref)."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        scheme = parsed.scheme.lower() or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")

        # Filtrar parámetros de tracking
        tracking_prefixes = ("utm_", "fbclid", "gclid", "ref", "source", "_hs")
        filtered_query = [
            (k, v)
            for k, v in parse_qsl(parsed.query, keep_blank_values=False)
            if not any(k.lower().startswith(p) for p in tracking_prefixes)
        ]
        filtered_query.sort()
        new_query = "&".join(f"{k}={v}" for k, v in filtered_query)

        return urlunparse((scheme, netloc, path, "", new_query, ""))
    except Exception:
        return url.strip().rstrip("/").lower()


def _normalize_title(title: str) -> str:
    """Normaliza un título eliminando acentos, espacios y caracteres especiales."""
    if not title:
        return ""
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", title.lower())
    without_accents = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", without_accents)


def _url_hash(url: str) -> str:
    """Calcula el hash SHA-256 truncado de una URL normalizada."""
    norm = _normalize_url(url)
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]


def save_trend(
    trend_data: Dict[str, Any],
    card_data: Optional[Dict[str, Any]] = None
) -> int:
    """Registra una tendencia en historial_envios y retorna su ID."""
    url = trend_data.get("url", "")
    title = trend_data.get("title", "")
    uhash = _url_hash(url)
    norm_title = _normalize_title(title)
    card_json = json.dumps(card_data, ensure_ascii=False) if card_data else None

    with _get_connection() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO historial_envios
                (url, url_hash, title, source, category, score, sent_at, card_data, normalized_title)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                url,
                uhash,
                title,
                trend_data.get("source", ""),
                trend_data.get("category", ""),
                float(trend_data.get("metric_score", 0.0)),
                datetime.utcnow().isoformat(),
                card_json,
                norm_title,
            ),
        )
        if cur.lastrowid:
            return cur.lastrowid

        # Si ya existía por hash, actualizar card_data y fecha y devolver su id
        row = conn.execute(
            "SELECT id FROM historial_envios WHERE url_hash = ?",
            (uhash,),
        ).fetchone()
        if row:
            if card_json:
                conn.execute(
                    "UPDATE historial_envios SET card_data = ?, sent_at = ? WHERE id = ?",
                    (card_json, datetime.utcnow().isoformat(), row["id"]),
                )
            return row["id"]
        return -1


def trend_exists(
    url: str,
    title: Optional[str] = None,
    days_cooldown: Optional[int] = 30
) -> bool:
    """Verifica si una tendencia ya fue enviada previamente dentro de la ventana de cooldown.

    Args:
        url: URL de la tendencia.
        title: Título opcional para verificación secundaria por nombre.
        days_cooldown: Ventana en días para considerar duplicada una tendencia (por defecto 30 días).
                       Si es None o <= 0, verifica en todo el historial.
    """
    uhash = _url_hash(url)
    norm_title = _normalize_title(title) if title else None

    with _get_connection() as conn:
        if days_cooldown and days_cooldown > 0:
            cutoff = (datetime.utcnow() - timedelta(days=days_cooldown)).isoformat()
            # 1. Comprobación por URL normalizada dentro de la ventana
            row = conn.execute(
                """
                SELECT 1 FROM historial_envios
                WHERE url_hash = ? AND sent_at >= ?
                LIMIT 1
                """,
                (uhash, cutoff),
            ).fetchone()
            if row:
                return True

            # 2. Comprobación por título normalizado dentro de la ventana
            if norm_title and len(norm_title) >= 5:
                row = conn.execute(
                    """
                    SELECT 1 FROM historial_envios
                    WHERE normalized_title = ? AND sent_at >= ?
                    LIMIT 1
                    """,
                    (norm_title, cutoff),
                ).fetchone()
                if row:
                    return True
        else:
            # Comprobación histórica total
            row = conn.execute(
                "SELECT 1 FROM historial_envios WHERE url_hash = ? LIMIT 1",
                (uhash,),
            ).fetchone()
            if row:
                return True
            if norm_title and len(norm_title) >= 5:
                row = conn.execute(
                    "SELECT 1 FROM historial_envios WHERE normalized_title = ? LIMIT 1",
                    (norm_title,),
                ).fetchone()
                if row:
                    return True

    return False


def get_trend_by_id(trend_id: int) -> Optional[Dict[str, Any]]:
    """Obtiene una tendencia del historial por su ID, deserializando card_data si existe."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM historial_envios WHERE id = ?", (trend_id,)
        ).fetchone()
        if not row:
            return None
        data = dict(row)
        if data.get("card_data"):
            try:
                data["card_data"] = json.loads(data["card_data"])
            except Exception:
                pass
        return data


def get_favorite_or_trend(identifier: int, user_id: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """Busca una tendencia por ID tanto en tendencias_guardadas como en historial_envios, deserializando card_data/llm_analysis."""
    with _get_connection() as conn:
        # 1. Buscar en tendencias_guardadas por id (filtrando por user_id si se especifica)
        if user_id is not None:
            uid = int(user_id) if str(user_id).isdigit() else user_id
            row = conn.execute("SELECT * FROM tendencias_guardadas WHERE id = ? AND user_id = ?", (identifier, uid)).fetchone()
        else:
            row = conn.execute("SELECT * FROM tendencias_guardadas WHERE id = ?", (identifier,)).fetchone()
        if row:
            data = dict(row)
            card_dict = None
            if data.get("llm_analysis"):
                try:
                    card_dict = json.loads(data["llm_analysis"]) if isinstance(data["llm_analysis"], str) else data["llm_analysis"]
                except Exception:
                    pass
            if not card_dict and data.get("url_hash"):
                h_row = conn.execute("SELECT card_data FROM historial_envios WHERE url_hash = ?", (data["url_hash"],)).fetchone()
                if h_row and h_row["card_data"]:
                    try:
                        card_dict = json.loads(h_row["card_data"]) if isinstance(h_row["card_data"], str) else h_row["card_data"]
                    except Exception:
                        pass
            data["card_data"] = card_dict
            return data

        # 2. Buscar en historial_envios por id
        h_row = conn.execute("SELECT * FROM historial_envios WHERE id = ?", (identifier,)).fetchone()
        if h_row:
            data = dict(h_row)
            if data.get("card_data"):
                try:
                    data["card_data"] = json.loads(data["card_data"]) if isinstance(data["card_data"], str) else data["card_data"]
                except Exception:
                    pass
            return data

        return None


def get_recent_sent_trends(limit: int = 20) -> List[Dict[str, Any]]:
    """Retorna las tendencias enviadas recientemente ordenadas cronológicamente."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, url, title, source, category, score, sent_at
            FROM historial_envios
            ORDER BY sent_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_daily_catalog_trends(limit: int = 5) -> List[Dict[str, Any]]:
    """Retorna el lote de 3 a 5 tendencias del catálogo más reciente en orden cronológico (id ASC)."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, url, title, source, category, score, sent_at, card_data
            FROM (
                SELECT * FROM historial_envios
                ORDER BY id DESC
                LIMIT ?
            )
            ORDER BY id ASC
            """,
            (max(3, min(limit, 5)),)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("card_data"):
                try:
                    d["card_data"] = json.loads(d["card_data"]) if isinstance(d["card_data"], str) else d["card_data"]
                except Exception:
                    pass
            result.append(d)
        return result


def mark_as_favorite(trend_id: int, message_id: Optional[int] = None, user_id: Optional[Any] = None) -> bool:
    """Copia una entrada del historial a tendencias_guardadas como favorito, asociando user_id y message_id."""
    if user_id is None:
        return False
    uid = int(user_id) if str(user_id).isdigit() else user_id
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM historial_envios WHERE id = ?", (trend_id,)
        ).fetchone()
        if not row:
            return False

        # Obtener título limpio preferente desde card_data si existe
        clean_title = row["title"]
        if "card_data" in row.keys() and row["card_data"]:
            try:
                cd = json.loads(row["card_data"]) if isinstance(row["card_data"], str) else row["card_data"]
                if cd and isinstance(cd, dict) and cd.get("title") and len(str(cd.get("title")).strip()) >= 3:
                    card_title = str(cd.get("title")).strip()
                    from app.context_reader import business_context
                    if (
                        " vs " in clean_title.lower()
                        or "demanda" in clean_title.lower()
                        or len(clean_title) < 4
                        or not business_context.is_relevant_to_business(clean_title)
                    ):
                        clean_title = card_title
            except Exception:
                pass

        conn.execute(
            """
            INSERT INTO tendencias_guardadas
                (user_id, url, url_hash, title, source, category, score, llm_analysis, saved_at, is_favorite, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(user_id, url_hash) DO UPDATE SET
                title = excluded.title,
                message_id = COALESCE(excluded.message_id, tendencias_guardadas.message_id),
                saved_at = excluded.saved_at,
                is_favorite = 1
            """,
            (
                uid,
                row["url"],
                row["url_hash"],
                clean_title,
                row["source"],
                row["category"],
                row["score"],
                row["card_data"] if "card_data" in row.keys() else None,
                datetime.utcnow().isoformat(),
                message_id,
            ),
        )
        return True


def add_favorite(trend_id: int, user_id: Any, message_id: Optional[int] = None) -> bool:
    """Registra una tendencia como favorita vinculada exclusivamente al user_id."""
    return mark_as_favorite(trend_id=trend_id, user_id=user_id, message_id=message_id)


def remove_favorite(user_id: Any, trend_id: int) -> bool:
    """Elimina una tendencia de favoritos en tendencias_guardadas filtrando estrictamente con WHERE user_id = ?."""
    if user_id is None:
        return False
    uid = int(user_id) if str(user_id).isdigit() else user_id
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM tendencias_guardadas
            WHERE (id = ? OR url_hash IN (SELECT url_hash FROM historial_envios WHERE id = ?))
              AND user_id = ?
            """,
            (trend_id, trend_id, uid)
        )
        return cursor.rowcount > 0


def get_favorites(user_id: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Obtiene la lista de tendencias marcadas como favoritas del usuario especificado usando estrictamente WHERE user_id = ?."""
    if user_id is None:
        return []
    uid = int(user_id) if str(user_id).isdigit() else user_id
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tendencias_guardadas WHERE is_favorite = 1 AND user_id = ? ORDER BY saved_at DESC",
            (uid,)
        ).fetchall()
        favs = []
        for r in rows:
            item = dict(r)
            if item.get("llm_analysis"):
                try:
                    item["llm_analysis"] = json.loads(item["llm_analysis"])
                except Exception:
                    pass
            favs.append(item)
        return favs


def get_daily_history(date: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """Retorna las tendencias registradas en una fecha determinada (hoy por defecto)."""
    target = (date or datetime.utcnow()).strftime("%Y-%m-%d")
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM historial_envios WHERE sent_at LIKE ? ORDER BY score DESC",
            (f"{target}%",),
        ).fetchall()
        return [dict(r) for r in rows]


def set_user_zone(
    chat_id: str,
    zone: Optional[str],
    zona_local: Optional[str] = None,
    zona_pais: Optional[str] = None,
    zonas: Optional[List[Dict[str, Any]]] = None
) -> None:
    """Guarda o actualiza la zona geográfica preferida del usuario en SQLite (con soporte jerárquico y multizona)."""
    val = str(zone).strip() if zone else ""
    z_local = str(zona_local).strip() if (zona_local is not None and str(zona_local).strip().lower() not in ("none", "null")) else None
    z_pais = str(zona_pais).strip() if (zona_pais is not None and str(zona_pais).strip().lower() not in ("none", "null")) else None

    clean_zonas: List[Dict[str, Any]] = []
    if zonas and isinstance(zonas, list):
        for item in zonas:
            if isinstance(item, dict):
                loc = item.get("zona_local")
                p = item.get("zona_pais")
                loc_clean = str(loc).strip() if (loc is not None and str(loc).strip().lower() not in ("none", "null", "")) else None
                p_clean = str(p).strip() if (p is not None and str(p).strip().lower() not in ("none", "null", "")) else None
                if loc_clean or p_clean:
                    clean_zonas.append({"zona_local": loc_clean, "zona_pais": p_clean or loc_clean})

    if not clean_zonas:
        if z_local or z_pais:
            clean_zonas = [{"zona_local": z_local, "zona_pais": z_pais or z_local or "Global"}]
        else:
            clean_zonas = [{"zona_local": None, "zona_pais": "Global"}]

    if clean_zonas:
        z_local = clean_zonas[0].get("zona_local")
        z_pais = clean_zonas[0].get("zona_pais") or "Global"
        if not val or val == "Global":
            parts = []
            for z in clean_zonas:
                zl = z.get("zona_local")
                zp = z.get("zona_pais") or ""
                if zl and str(zl).strip():
                    if zp and str(zp).strip() and str(zp).lower() != str(zl).lower() and str(zp).lower() not in str(zl).lower():
                        parts.append(f"{str(zl).strip()}, {str(zp).strip()}")
                    else:
                        parts.append(str(zl).strip())
                else:
                    parts.append(str(zp).strip())
            val = " | ".join(parts)

    zonas_json_str = json.dumps(clean_zonas, ensure_ascii=False)

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, zona_local, zona_pais, zonas_json, industria, onboarding_step, updated_at)
            VALUES (?, ?, ?, ?, ?, '', 'STEP_INDUSTRY', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                zona_preferida = excluded.zona_preferida,
                zona_local = excluded.zona_local,
                zona_pais = excluded.zona_pais,
                zonas_json = excluded.zonas_json,
                onboarding_step = 'STEP_INDUSTRY',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), val, z_local or "", z_pais or "", zonas_json_str, datetime.utcnow().isoformat())
        )


def get_user_zone(chat_id: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Obtiene la zona geográfica preferida del usuario (None si está vacía)."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT zona_preferida, zona_local, zona_pais FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row and row["zona_preferida"] and str(row["zona_preferida"]).strip():
                return str(row["zona_preferida"]).strip()
            return default

        # Si no se especificó chat_id o no existe aún, tomar la última guardada no vacía
        row = conn.execute(
            "SELECT zona_preferida, zona_local, zona_pais FROM configuracion_usuario WHERE zona_preferida IS NOT NULL AND zona_preferida != '' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row and row["zona_preferida"] and str(row["zona_preferida"]).strip():
            return str(row["zona_preferida"]).strip()

        return default or "Global"


def get_user_zone_hierarchy(chat_id: Optional[str] = None) -> tuple[str, str]:
    """Obtiene la tupla (zona_local, zona_pais) del usuario para resolución geográfica jerárquica."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT zona_preferida, zona_local, zona_pais, zonas_json FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT zona_preferida, zona_local, zona_pais, zonas_json FROM configuracion_usuario WHERE (zona_preferida IS NOT NULL AND zona_preferida != '') OR (zona_local IS NOT NULL AND zona_local != '') ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()

        if row:
            keys = row.keys()
            raw_json = row["zonas_json"] if "zonas_json" in keys and row["zonas_json"] else ""
            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list) and parsed:
                        first = parsed[0]
                        if isinstance(first, dict):
                            loc = str(first.get("zona_local") or "").strip()
                            p = str(first.get("zona_pais") or "").strip()
                            if loc:
                                return (loc, p or loc)
                except Exception:
                    pass

            z_loc = str(row["zona_local"]).strip() if "zona_local" in keys and row["zona_local"] else ""
            z_p = str(row["zona_pais"]).strip() if "zona_pais" in keys and row["zona_pais"] else ""
            z_pref = str(row["zona_preferida"]).strip() if "zona_preferida" in keys and row["zona_preferida"] else ""

            if not z_loc:
                z_loc = z_pref or "Global"
            if not z_p:
                z_p = z_pref or "Global"
            return (z_loc, z_p)

        return ("Global", "Global")


def get_user_zones(chat_id: Optional[str] = None) -> List[Dict[str, str]]:
    """Obtiene la lista de zonas configuradas [{'zona_local': str, 'zona_pais': str}, ...] para el usuario."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT zona_preferida, zona_local, zona_pais, zonas_json FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT zona_preferida, zona_local, zona_pais, zonas_json FROM configuracion_usuario WHERE (zona_preferida IS NOT NULL AND zona_preferida != '') OR (zona_local IS NOT NULL AND zona_local != '') ORDER BY updated_at DESC LIMIT 1"
            ).fetchone()

        if row:
            keys = row.keys()
            raw_json = row["zonas_json"] if "zonas_json" in keys and row["zonas_json"] else ""
            if raw_json:
                try:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list) and parsed:
                        clean = []
                        for item in parsed:
                            if isinstance(item, dict):
                                loc = str(item.get("zona_local") or "").strip()
                                p = str(item.get("zona_pais") or "").strip()
                                if loc:
                                    clean.append({"zona_local": loc, "zona_pais": p or loc})
                        if clean:
                            return clean
                except Exception:
                    pass

            z_loc = str(row["zona_local"]).strip() if "zona_local" in keys and row["zona_local"] else ""
            z_p = str(row["zona_pais"]).strip() if "zona_pais" in keys and row["zona_pais"] else ""
            z_pref = str(row["zona_preferida"]).strip() if "zona_preferida" in keys and row["zona_preferida"] else ""
            if not z_loc:
                z_loc = z_pref or "Global"
            if not z_p:
                z_p = z_pref or "Global"
            return [{"zona_local": z_loc, "zona_pais": z_p}]

        return [{"zona_local": "Global", "zona_pais": "Global"}]


def set_user_industry(
    chat_id: str,
    industry: Optional[str],
    industria_exacta: Optional[str] = None,
    categoria_api: Optional[str] = None
) -> None:
    """Guarda o actualiza la industria preferida, la industria exacta y la categoría de API del usuario en SQLite, y avanza a STEP_SCHEDULE."""
    val = str(industry).strip() if industry else ""
    exact_val = str(industria_exacta).strip() if industria_exacta else val
    cat_val = str(categoria_api).strip().lower() if categoria_api else "general"
    if cat_val not in ("tech", "retail", "general"):
        cat_val = "general"

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, industria, industria_exacta, categoria_api, onboarding_step, updated_at)
            VALUES (?, '', ?, ?, ?, 'STEP_SCHEDULE', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                industria = excluded.industria,
                industria_exacta = excluded.industria_exacta,
                categoria_api = excluded.categoria_api,
                onboarding_step = 'STEP_SCHEDULE',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), val, exact_val, cat_val, datetime.utcnow().isoformat())
        )


def set_user_schedule(chat_id: str, schedule_time: str) -> None:
    """Guarda la hora preferida del usuario (formato HH:MM) y finaliza el onboarding marcando COMPLETED."""
    val = str(schedule_time).strip() or "10:00"
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, schedule_time, onboarding_step, updated_at)
            VALUES (?, ?, 'COMPLETED', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                schedule_time = excluded.schedule_time,
                onboarding_step = 'COMPLETED',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), val, datetime.utcnow().isoformat())
        )


def get_user_schedule(chat_id: Optional[str] = None, default: str = "10:00") -> str:
    """Obtiene la hora programada del usuario (formato HH:MM, por defecto 10:00)."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT schedule_time FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row and row["schedule_time"] and str(row["schedule_time"]).strip():
                return str(row["schedule_time"]).strip()
        return default


def set_user_freelance_profile(
    chat_id: str,
    role: str,
    skills: Union[List[str], str],
    keywords: str = ""
) -> None:
    """Guarda el perfil profesional freelance del usuario y finaliza exitosamente el onboarding (COMPLETED)."""
    if isinstance(skills, list):
        skills_json = json.dumps(skills, ensure_ascii=False)
    else:
        skills_json = json.dumps([s.strip() for s in str(skills).split(",") if s.strip()], ensure_ascii=False)

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, freelance_role, freelance_skills, freelance_keywords, onboarding_step, updated_at)
            VALUES (?, ?, ?, ?, 'COMPLETED', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                freelance_role = excluded.freelance_role,
                freelance_skills = excluded.freelance_skills,
                freelance_keywords = excluded.freelance_keywords,
                onboarding_step = 'COMPLETED',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), str(role).strip(), skills_json, str(keywords).strip(), datetime.utcnow().isoformat())
        )


def get_user_freelance_profile(chat_id: Optional[str] = None) -> Dict[str, Any]:
    """Obtiene el perfil profesional freelance configurado del usuario."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT freelance_role, freelance_skills, freelance_keywords FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row:
                raw_skills = row["freelance_skills"] or "[]"
                try:
                    skills_list = json.loads(raw_skills) if isinstance(raw_skills, str) else []
                except Exception:
                    skills_list = []
                return {
                    "role": str(row["freelance_role"] or "").strip(),
                    "skills": skills_list if isinstance(skills_list, list) else [],
                    "keywords": str(row["freelance_keywords"] or "").strip()
                }
        return {"role": "", "skills": [], "keywords": ""}


def get_user_industry(chat_id: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Obtiene la industria preferida del usuario (prioriza industria_exacta si existe)."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT industria, industria_exacta FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row:
                if "industria_exacta" in row.keys() and row["industria_exacta"] and str(row["industria_exacta"]).strip():
                    return str(row["industria_exacta"]).strip()
                if row["industria"] and str(row["industria"]).strip():
                    return str(row["industria"]).strip()
            return default

        row = conn.execute(
            "SELECT industria, industria_exacta FROM configuracion_usuario WHERE (industria_exacta IS NOT NULL AND industria_exacta != '') OR (industria IS NOT NULL AND industria != '') ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row:
            if "industria_exacta" in row.keys() and row["industria_exacta"] and str(row["industria_exacta"]).strip():
                return str(row["industria_exacta"]).strip()
            if row["industria"] and str(row["industria"]).strip():
                return str(row["industria"]).strip()

        return default or "TI & Software B2B"


def get_user_exact_industry(chat_id: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Obtiene el nombre profesional exacto de la industria o tecnología del usuario."""
    return get_user_industry(chat_id, default=default)


def get_user_categoria_api(chat_id: Optional[str] = None, default: str = "general") -> str:
    """Obtiene la categoría de API del usuario ('tech', 'retail', 'general')."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT categoria_api FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row and "categoria_api" in row.keys() and row["categoria_api"] and str(row["categoria_api"]).strip():
                return str(row["categoria_api"]).strip().lower()
            return default

        row = conn.execute(
            "SELECT categoria_api FROM configuracion_usuario WHERE categoria_api IS NOT NULL AND categoria_api != '' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row and "categoria_api" in row.keys() and row["categoria_api"] and str(row["categoria_api"]).strip():
            return str(row["categoria_api"]).strip().lower()

        return default


def get_user_onboarding_step(chat_id: Optional[str] = None) -> str:
    """Retorna el estado actual de la máquina de estados (FSM) de onboarding:
    'STEP_ZONE', 'STEP_INDUSTRY', 'STEP_SCHEDULE', 'STEP_FREELANCE_PROFILE' o 'COMPLETED'.
    """
    if not chat_id:
        return "STEP_ZONE"
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT onboarding_step, zona_preferida, zona_local, zona_pais, industria, schedule_time, freelance_role FROM configuracion_usuario WHERE chat_id = ?",
            (str(chat_id),)
        ).fetchone()
        if not row:
            return "STEP_ZONE"
        keys = row.keys()
        if "onboarding_step" in keys and row["onboarding_step"]:
            st = str(row["onboarding_step"]).strip().upper()
            if st in ("STEP_ZONE", "STEP_INDUSTRY", "STEP_SCHEDULE", "STEP_FREELANCE_PROFILE", "COMPLETED"):
                return st
        # Inferencia de respaldo para registros preexistentes
        z_pref = str(row["zona_preferida"] or "").strip()
        z_loc = str(row["zona_local"] or "").strip()
        z_pais = str(row["zona_pais"] or "").strip()
        ind = str(row["industria"] or "").strip()
        has_zone = bool(z_pref or z_loc or z_pais)
        has_ind = bool(ind)
        has_sched = bool(str(row["schedule_time"] or "").strip())
        has_free = bool(str(row["freelance_role"] or "").strip())

        if has_zone and has_ind and has_sched:
            return "COMPLETED"
        elif has_zone and has_ind:
            return "STEP_SCHEDULE"
        elif has_zone:
            return "STEP_INDUSTRY"
        return "STEP_ZONE"


def set_user_onboarding_step(chat_id: str, step: str) -> None:
    """Actualiza explícitamente el paso de onboarding para el usuario."""
    st = step.strip().upper()
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, onboarding_step, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                onboarding_step = excluded.onboarding_step,
                updated_at = excluded.updated_at
            """,
            (str(chat_id), st, datetime.utcnow().isoformat())
        )


def reset_user_config(chat_id: str) -> None:
    """Borra todos los campos de configuración del usuario en SQLite para reiniciar el onboarding desde STEP_ZONE."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (
                chat_id, zona_preferida, zona_local, zona_pais, zonas_json,
                industria, industria_exacta, categoria_api,
                schedule_time, freelance_role, freelance_skills, freelance_keywords,
                onboarding_step, updated_at
            )
            VALUES (?, '', '', '', '[]', '', '', 'general', '10:00', '', '[]', '', 'STEP_ZONE', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                zona_preferida = '',
                zona_local = '',
                zona_pais = '',
                zonas_json = '[]',
                industria = '',
                industria_exacta = '',
                categoria_api = 'general',
                schedule_time = '10:00',
                freelance_role = '',
                freelance_skills = '[]',
                freelance_keywords = '',
                onboarding_step = 'STEP_ZONE',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), datetime.utcnow().isoformat())
        )


def get_users_by_schedule(time_str: str) -> List[Dict[str, Any]]:
    """Consulta en SQLite todos los usuarios con perfil COMPLETED cuyo schedule_time coincida exactamente con time_str (HH:MM)."""
    norm_time = time_str.strip()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT chat_id,
                   COALESCE(NULLIF(TRIM(zona_preferida), ''), 'Global') AS zona_preferida,
                   COALESCE(NULLIF(TRIM(zona_local), ''), NULLIF(TRIM(zona_preferida), ''), 'Global') AS zona_local,
                   COALESCE(NULLIF(TRIM(zona_pais), ''), NULLIF(TRIM(zona_preferida), ''), 'Global') AS zona_pais,
                   COALESCE(NULLIF(TRIM(zonas_json), ''), '[]') AS zonas_json,
                   COALESCE(NULLIF(TRIM(industria_exacta), ''), NULLIF(TRIM(industria), ''), 'TI & Software B2B') AS industria,
                   COALESCE(NULLIF(TRIM(industria_exacta), ''), NULLIF(TRIM(industria), ''), 'TI & Software B2B') AS industria_exacta,
                   COALESCE(NULLIF(TRIM(categoria_api), ''), 'general') AS categoria_api,
                   COALESCE(NULLIF(TRIM(schedule_time), ''), '10:00') AS schedule_time,
                   COALESCE(NULLIF(TRIM(freelance_role), ''), '') AS freelance_role,
                   COALESCE(NULLIF(TRIM(freelance_skills), ''), '[]') AS freelance_skills,
                   COALESCE(NULLIF(TRIM(freelance_keywords), ''), '') AS freelance_keywords,
                   updated_at
            FROM configuracion_usuario
            WHERE chat_id IS NOT NULL AND TRIM(chat_id) != ''
              AND onboarding_step = 'COMPLETED'
              AND (schedule_time = ? OR (schedule_time = '10:00' AND ? = '10:00'))
            ORDER BY updated_at DESC
            """,
            (norm_time, norm_time)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            raw_z = d.get("zonas_json") or "[]"
            try:
                parsed_z = json.loads(raw_z)
                d["zonas"] = parsed_z if isinstance(parsed_z, list) else []
            except Exception:
                d["zonas"] = []
            if not d["zonas"]:
                d["zonas"] = [{"zona_local": d.get("zona_local", "Global"), "zona_pais": d.get("zona_pais", "Global")}]
            result.append(d)
        return result


def get_all_configured_users() -> List[Dict[str, Any]]:
    """Consulta en SQLite a todos los usuarios con perfil registrado (asignando industria por defecto si no está definida)."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT chat_id,
                   COALESCE(NULLIF(TRIM(zona_preferida), ''), 'Global') AS zona_preferida,
                   COALESCE(NULLIF(TRIM(zona_local), ''), NULLIF(TRIM(zona_preferida), ''), 'Global') AS zona_local,
                   COALESCE(NULLIF(TRIM(zona_pais), ''), NULLIF(TRIM(zona_preferida), ''), 'Global') AS zona_pais,
                   COALESCE(NULLIF(TRIM(zonas_json), ''), '[]') AS zonas_json,
                   COALESCE(NULLIF(TRIM(industria_exacta), ''), NULLIF(TRIM(industria), ''), 'TI & Software B2B') AS industria,
                   COALESCE(NULLIF(TRIM(industria_exacta), ''), NULLIF(TRIM(industria), ''), 'TI & Software B2B') AS industria_exacta,
                   COALESCE(NULLIF(TRIM(categoria_api), ''), 'general') AS categoria_api,
                   updated_at
            FROM configuracion_usuario
            WHERE chat_id IS NOT NULL AND TRIM(chat_id) != ''
            ORDER BY updated_at DESC
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            # Parsear zonas como lista
            raw_z = d.get("zonas_json") or "[]"
            try:
                parsed_z = json.loads(raw_z)
                d["zonas"] = parsed_z if isinstance(parsed_z, list) else []
            except Exception:
                d["zonas"] = []
            if not d["zonas"]:
                d["zonas"] = [{"zona_local": d.get("zona_local", "Global"), "zona_pais": d.get("zona_pais", "Global")}]
            result.append(d)
        return result


# ============================================================================
# Registro de Tarjetas Enviadas, Límites Diarios y Caducidad (TTL 7 Días)
# ============================================================================

def record_sent_card(
    chat_id: str,
    message_id: int,
    chat_type: str = "private",
    created_at: Optional[datetime] = None
) -> int:
    """Registra una tarjeta enviada para seguimiento de límites diarios y caducidad TTL."""
    now_str = (created_at or datetime.utcnow()).isoformat()
    with _get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO registro_tarjetas_enviadas (chat_id, message_id, chat_type, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (str(chat_id), int(message_id), str(chat_type), now_str)
        )
        return cursor.lastrowid


def get_user_daily_card_count(chat_id: str, target_date: Optional[str] = None) -> int:
    """Retorna la cantidad de tarjetas enviadas hoy (o en target_date 'YYYY-MM-DD') a un chat privado."""
    day_str = target_date or datetime.utcnow().strftime("%Y-%m-%d")
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM registro_tarjetas_enviadas
            WHERE chat_id = ? AND created_at LIKE ?
            """,
            (str(chat_id), f"{day_str}%")
        ).fetchone()
        return int(row["total"]) if row else 0


def get_expired_card_messages(days: int = 7) -> List[Dict[str, Any]]:
    """Retorna los registros de tarjetas enviadas que superan los 'days' días de antigüedad."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    cutoff_str = cutoff.isoformat()
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, chat_id, message_id, chat_type, created_at
            FROM registro_tarjetas_enviadas
            WHERE created_at <= ?
            ORDER BY created_at ASC
            """,
            (cutoff_str,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_card_record(record_id: int) -> None:
    """Elimina el registro de una tarjeta tras haberse borrado físicamente en Telegram."""
    with _get_connection() as conn:
        conn.execute(
            "DELETE FROM registro_tarjetas_enviadas WHERE id = ?",
            (int(record_id),)
        )


def get_last_sent_card_message(chat_id: str) -> Optional[int]:
    """Retorna el message_id de la última tarjeta enviada al chat indicado."""
    with _get_connection() as conn:
        row = conn.execute(
            """
            SELECT message_id
            FROM registro_tarjetas_enviadas
            WHERE chat_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(chat_id),)
        ).fetchone()
        return int(row["message_id"]) if row else None


# ============================================================================
# Gestión y Persistencia: Empresas Demandantes B2B Diarias
# ============================================================================

def save_b2b_companies(companies: List[Dict[str, Any]], discovered_date: str) -> None:
    """Guarda o actualiza las empresas demandantes descubiertas para una fecha específica."""
    now_iso = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        incoming_ids = [c.get("id") or f"demanda_{hashlib.md5(c.get('company', '').encode('utf-8')).hexdigest()[:8]}" for c in companies]
        if incoming_ids:
            placeholders = ",".join("?" for _ in incoming_ids)
            conn.execute(
                f"DELETE FROM b2b_empresas_demandantes WHERE discovered_date = ? AND company_id NOT IN ({placeholders})",
                [str(discovered_date), *incoming_ids]
            )
        for c in companies:
            c_id = c.get("id") or f"demanda_{hashlib.md5(c.get('company', '').encode('utf-8')).hexdigest()[:8]}"
            tags_json = json.dumps(c.get("tags", []), ensure_ascii=False)
            comp_json = json.dumps(c.get("comparison_points", []), ensure_ascii=False)
            conn.execute(
                """
                INSERT INTO b2b_empresas_demandantes (
                    company_id, company_name, sector, priority, status_badge,
                    budget, problem, solution, tags_json, contact_email,
                    contact_web, linkedin_url, linkedin_status, source_url,
                    financial_quote, scope_summary, comparison_points_json,
                    demand_source_type, demand_source_label, demand_evidence_url,
                    discovered_date, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(company_id) DO UPDATE SET
                    company_name = excluded.company_name,
                    sector = excluded.sector,
                    priority = excluded.priority,
                    status_badge = excluded.status_badge,
                    budget = excluded.budget,
                    problem = excluded.problem,
                    solution = excluded.solution,
                    tags_json = excluded.tags_json,
                    contact_email = excluded.contact_email,
                    contact_web = excluded.contact_web,
                    linkedin_url = excluded.linkedin_url,
                    linkedin_status = excluded.linkedin_status,
                    source_url = excluded.source_url,
                    financial_quote = excluded.financial_quote,
                    scope_summary = excluded.scope_summary,
                    comparison_points_json = excluded.comparison_points_json,
                    demand_source_type = excluded.demand_source_type,
                    demand_source_label = excluded.demand_source_label,
                    demand_evidence_url = excluded.demand_evidence_url,
                    discovered_date = excluded.discovered_date
                """,
                (
                    c_id,
                    c.get("company", ""),
                    c.get("sector", "Tecnología B2B"),
                    c.get("priority", "Alta"),
                    c.get("status_badge", "Activo"),
                    c.get("budget", "$10,000 - $20,000 USD"),
                    c.get("problem", ""),
                    c.get("solution", ""),
                    tags_json,
                    c.get("contact_email", ""),
                    c.get("contact_web", ""),
                    c.get("linkedin_company_url", c.get("linkedin_url", "")),
                    c.get("linkedin_status", "active"),
                    c.get("source_url", ""),
                    c.get("financial_quote", ""),
                    c.get("scope_summary", ""),
                    comp_json,
                    c.get("demand_source_type", ""),
                    c.get("demand_source_label", ""),
                    c.get("demand_evidence_url", ""),
                    str(discovered_date),
                    now_iso
                )
            )


def get_b2b_companies_by_date(discovered_date: str) -> List[Dict[str, Any]]:
    """Retorna las empresas demandantes descubiertas en la fecha indicada (formato YYYY-MM-DD)."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM b2b_empresas_demandantes
            WHERE discovered_date = ?
            ORDER BY id ASC
            """,
            (str(discovered_date),)
        ).fetchall()

        results = []
        for r in rows:
            d = dict(r)
            try:
                tags = json.loads(d.get("tags_json") or "[]")
            except Exception:
                tags = []
            try:
                comp = json.loads(d.get("comparison_points_json") or "[]")
            except Exception:
                comp = []
            results.append({
                "id": d.get("company_id"),
                "company": d.get("company_name"),
                "sector": d.get("sector"),
                "priority": d.get("priority"),
                "status_badge": d.get("status_badge"),
                "budget": d.get("budget"),
                "problem": d.get("problem"),
                "solution": d.get("solution"),
                "tags": tags,
                "contact_email": d.get("contact_email"),
                "contact_web": d.get("contact_web"),
                "linkedin_company_url": d.get("linkedin_url"),
                "linkedin_status": d.get("linkedin_status", "active"),
                "source_url": d.get("source_url"),
                "financial_quote": d.get("financial_quote"),
                "scope_summary": d.get("scope_summary"),
                "comparison_points": comp,
                "demand_source_type": d.get("demand_source_type", ""),
                "demand_source_label": d.get("demand_source_label", ""),
                "demand_evidence_url": d.get("demand_evidence_url", ""),
                "discovered_date": d.get("discovered_date")
            })
        return results


def get_recent_b2b_company_names(limit: int = 50) -> List[str]:
    """Retorna los nombres de las empresas descubiertas recientemente para evitar repeticiones."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT company_name FROM b2b_empresas_demandantes
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(limit),)
        ).fetchall()
        return [str(r["company_name"]) for r in rows if r["company_name"]]


def purge_obsolete_b2b_companies(valid_ids: List[str]) -> int:
    """Elimina de la base de datos cualquier empresa que no pertenezca a la lista de IDs autorizados."""
    if not valid_ids:
        return 0
    with _get_connection() as conn:
        placeholders = ",".join("?" for _ in valid_ids)
        cur = conn.execute(
            f"DELETE FROM b2b_empresas_demandantes WHERE company_id NOT IN ({placeholders})",
            valid_ids
        )
        conn.commit()
        return cur.rowcount


def save_enterprise_event(event_data: Dict[str, Any]) -> int:
    """Inserta o actualiza un evento empresarial en SQLite."""
    evt_id = str(event_data.get("id") or event_data.get("event_id") or "").strip()
    if not evt_id:
        import hashlib
        title = event_data.get("title", "")
        evt_id = "evt_" + hashlib.md5(title.encode("utf-8")).hexdigest()[:12]

    tags = event_data.get("tags") or []
    tags_json = json.dumps(tags, ensure_ascii=False) if isinstance(tags, list) else "[]"

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO eventos_empresariales
                (event_id, org, access_label, title, fixed_date_str, days_ahead, hour_str,
                 venue, target_audience, requirements, tags_json, platform_name,
                 platform_domain, platform_mode, registration_url, info_summary, created_at, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_id) DO UPDATE SET
                org = excluded.org,
                access_label = excluded.access_label,
                title = excluded.title,
                fixed_date_str = excluded.fixed_date_str,
                days_ahead = excluded.days_ahead,
                hour_str = excluded.hour_str,
                venue = excluded.venue,
                target_audience = excluded.target_audience,
                requirements = excluded.requirements,
                tags_json = excluded.tags_json,
                platform_name = excluded.platform_name,
                platform_domain = excluded.platform_domain,
                platform_mode = excluded.platform_mode,
                registration_url = excluded.registration_url,
                info_summary = excluded.info_summary,
                is_active = excluded.is_active
            """,
            (
                evt_id,
                str(event_data.get("org", "Big Tech Community")),
                str(event_data.get("access_label", "Registro Empresarial")),
                str(event_data.get("title", "Cumbre de Tecnología")),
                str(event_data.get("fixed_date_str", "")),
                int(event_data.get("days_ahead", 15)),
                str(event_data.get("hour_str", "09:00 hrs a 18:00 hrs")),
                str(event_data.get("venue", "Ciudad de México")),
                str(event_data.get("target_audience", "")),
                str(event_data.get("requirements", "")),
                tags_json,
                str(event_data.get("platform_name", "Portal Oficial")),
                str(event_data.get("platform_domain", "")),
                str(event_data.get("platform_mode", "Presencial · Sede Corporativa")),
                str(event_data.get("registration_url", "")),
                str(event_data.get("info_summary", "")),
                datetime.utcnow().isoformat(),
                int(event_data.get("is_active", 1)),
            ),
        )
        conn.commit()
        return 1


def get_active_enterprise_events() -> List[Dict[str, Any]]:
    """Retorna todos los eventos corporativos activos ordenados por ID."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM eventos_empresariales
            WHERE is_active = 1
            ORDER BY id ASC
            """
        ).fetchall()
        results: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            try:
                tags = json.loads(d.get("tags_json", "[]"))
            except Exception:
                tags = []
            results.append({
                "id": d.get("event_id"),
                "event_id": d.get("event_id"),
                "org": d.get("org"),
                "access_label": d.get("access_label"),
                "title": d.get("title"),
                "fixed_date_str": d.get("fixed_date_str"),
                "days_ahead": d.get("days_ahead", 15),
                "hour_str": d.get("hour_str", "09:00 hrs a 18:00 hrs"),
                "venue": d.get("venue"),
                "target_audience": d.get("target_audience"),
                "requirements": d.get("requirements"),
                "tags": tags,
                "platform_name": d.get("platform_name"),
                "platform_domain": d.get("platform_domain"),
                "platform_mode": d.get("platform_mode"),
                "registration_url": d.get("registration_url"),
                "info_summary": d.get("info_summary"),
                "created_at": d.get("created_at"),
            })
        return results


def delete_enterprise_event(event_id: str) -> bool:
    """Desactiva o elimina un evento de la base de datos."""
    with _get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM eventos_empresariales WHERE event_id = ?",
            (event_id,)
        )
        conn.commit()
        return cur.rowcount > 0


# ============================================================================
# Telemetría de Interacción de Usuarios & Retroalimentación de Demanda
# ============================================================================

def record_interaction_telemetry(
    user_id: str,
    chat_id: str,
    action_type: str,
    industry: str,
    details: str = "",
    db_path: Optional[Union[str, Path]] = None
) -> bool:
    """Registra una interacción de usuario en el búfer de telemetría de SQLite.
    
    action_type puede ser:
    - 'DEMANDA_QUOTE': Usuario simuló una cotización financiera / SOW.
    - 'DEMANDA_SCOPE': Usuario consultó la ficha técnica oficial.
    - 'INDUSTRY_SEARCH': Usuario configuró o consultó una industria específica.
    - 'FAVORITE_SAVED': Usuario guardó una tendencia en favoritos.
    """
    if not user_id or not action_type:
        return False

    resolved_path = Path(db_path) if db_path else None
    now_iso = datetime.now(timezone.utc).isoformat()
    clean_industry = str(industry or "").strip()
    clean_details = str(details or "").strip()

    try:
        with _get_connection(resolved_path) as conn:
            conn.execute(
                """
                INSERT INTO telemetria_interacciones (
                    user_id, chat_id, action_type, industry, details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (str(user_id), str(chat_id), action_type, clean_industry, clean_details, now_iso)
            )
            conn.commit()
            return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Telemetría] Error al registrar interacción: {e}")
        return False


def get_top_demanded_feedback(
    min_unique_users: int = 2,
    days_lookback: int = 30,
    limit: int = 10,
    db_path: Optional[Union[str, Path]] = None
) -> List[Dict[str, Any]]:
    """Agrega las industrias o temas con mayor tracción real entre usuarios únicos.
    
    Aplica protección Anti-Spam: Solo califica si al menos `min_unique_users` distintos
    han interactuado con la industria.
    """
    resolved_path = Path(db_path) if db_path else None
    since_date = (datetime.now(timezone.utc) - timedelta(days=days_lookback)).isoformat()

    query = """
        SELECT
            industry,
            COUNT(DISTINCT user_id) as unique_users,
            COUNT(id) as total_interactions,
            MAX(created_at) as last_interaction
        FROM telemetria_interacciones
        WHERE created_at >= ?
          AND industry != ''
          AND industry NOT IN ('TI & Software B2B', 'Global', 'general')
        GROUP BY industry
        HAVING COUNT(DISTINCT user_id) >= ?
        ORDER BY unique_users DESC, total_interactions DESC
        LIMIT ?
    """

    results: List[Dict[str, Any]] = []
    try:
        with _get_connection(resolved_path) as conn:
            rows = conn.execute(query, (since_date, min_unique_users, limit)).fetchall()
            for r in rows:
                results.append({
                    "industry": r["industry"],
                    "unique_users": int(r["unique_users"]),
                    "total_interactions": int(r["total_interactions"]),
                    "last_interaction": r["last_interaction"]
                })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"[Telemetría] Error agregando feedback: {e}")

    return results


def append_strategy_to_business_context(
    category_title: str,
    bullets: List[str],
    author: str = "Admin",
    context_path: Optional[Union[str, Path]] = None,
    context_reader: Optional[Any] = None
) -> Dict[str, Any]:
    """Anexa de forma segura y atómica una nueva línea estratégica a tendencias.txt.
    
    Aplica api-security-best-practices:
    - Validación perimetral contra inyecciones y lista negra de nota roja/deportes.
    - Idempotencia: evita agregar títulos duplicados.
    - Recarga en memoria en caliente (0 downtime).
    """
    clean_title = category_title.strip().lstrip("#").strip()
    if not clean_title or not bullets:
        return {"success": False, "error": "Título y viñetas obligatorias."}

    # 1. Blindaje de Seguridad Perimetral (Anti-Data Poisoning)
    full_text_to_check = f"{clean_title} " + " ".join(bullets)
    text_lower = full_text_to_check.lower()

    # Importar listas de seguridad dinámicamente para evitar dependencias circulares
    try:
        from app.connectors import _NON_TECH_BLACKLIST_TERMS
        if any(term in text_lower for term in _NON_TECH_BLACKLIST_TERMS):
            return {
                "success": False,
                "error": "RECHAZADO_POR_SEGURIDAD: Contenido incompatible con el perfil tecnológico (deportes, nota roja o farándula)."
            }
    except Exception:
        pass

    try:
        from app.security import _PROMPT_INJECTION_PATTERNS
        for pattern in _PROMPT_INJECTION_PATTERNS:
            if pattern.search(full_text_to_check):
                return {
                    "success": False,
                    "error": "RECHAZADO_POR_SEGURIDAD: Intento de inyección de prompt neutralizado."
                }
    except Exception:
        pass

    # 2. Resolver archivo de contexto
    target_path = Path(context_path) if context_path else (settings.BASE_DIR / "data" / "tendencias.txt")
    if not target_path.exists():
        # Fallback a raíz
        target_path = settings.BASE_DIR / "data" / "tendencias.txt"
        target_path.parent.mkdir(parents=True, exist_ok=True)
        if not target_path.exists():
            target_path.write_text("# FUENTE DE VERDAD DEL NEGOCIO\n\n", encoding="utf-8")

    current_text = target_path.read_text(encoding="utf-8")
    
    # 3. Idempotencia: evitar duplicados exactos
    if clean_title.lower() in current_text.lower():
        return {
            "success": True,
            "message": "La categoría ya se encuentra registrada en la fuente de verdad.",
            "category": clean_title,
            "already_existed": True
        }

    # 4. Formatear bloque Markdown
    formatted_block = f"\n\n## {clean_title}\n"
    for b in bullets:
        clean_b = b.strip().lstrip("-* ").strip()
        if clean_b:
            formatted_block += f"- {clean_b}\n"

    # 5. Escritura atómica
    try:
        with open(target_path, "a", encoding="utf-8") as f:
            f.write(formatted_block)
    except Exception as e:
        return {"success": False, "error": f"Error de escritura I/O: {e}"}

    # 6. Recarga en memoria en caliente (Hot Reload)
    reloaded_keywords = 0
    if context_reader is not None:
        context_reader.load_context()
        reloaded_keywords = len(context_reader.keywords)
    else:
        try:
            from app.context_reader import business_context
            business_context.load_context()
            reloaded_keywords = len(business_context.keywords)
        except Exception:
            pass

    import logging
    logging.getLogger(__name__).info(
        f"[Retroalimentación Negocio] Nueva línea '{clean_title}' anexada exitosamente por {author}. Palabras clave activas: {reloaded_keywords}"
    )

    return {
        "success": True,
        "category": clean_title,
        "bullets_added": len(bullets),
        "reloaded_keywords": reloaded_keywords
    }






