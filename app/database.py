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
from typing import Optional, List, Dict, Any
from datetime import datetime, date, timedelta
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
                chat_id          TEXT PRIMARY KEY,
                zona_preferida   TEXT NOT NULL DEFAULT 'Global',
                zona_local       TEXT NOT NULL DEFAULT '',
                zona_pais        TEXT NOT NULL DEFAULT '',
                zonas_json       TEXT NOT NULL DEFAULT '[]',
                industria        TEXT NOT NULL DEFAULT 'TI & Software B2B',
                industria_exacta TEXT NOT NULL DEFAULT '',
                categoria_api    TEXT NOT NULL DEFAULT 'general',
                onboarding_step  TEXT NOT NULL DEFAULT '',
                updated_at       TEXT NOT NULL
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
        if "onboarding_step" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN onboarding_step TEXT NOT NULL DEFAULT ''")


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

        conn.execute(
            """
            INSERT INTO tendencias_guardadas
                (user_id, url, url_hash, title, source, category, score, llm_analysis, saved_at, is_favorite, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(user_id, url_hash) DO UPDATE SET
                message_id = COALESCE(excluded.message_id, tendencias_guardadas.message_id),
                saved_at = excluded.saved_at,
                is_favorite = 1
            """,
            (
                uid,
                row["url"],
                row["url_hash"],
                row["title"],
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
    """Guarda o actualiza la industria preferida, la industria exacta y la categoría de API del usuario en SQLite."""
    val = str(industry).strip() if industry else ""
    exact_val = str(industria_exacta).strip() if industria_exacta else val
    cat_val = str(categoria_api).strip().lower() if categoria_api else "general"
    if cat_val not in ("tech", "retail", "general"):
        cat_val = "general"

    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, industria, industria_exacta, categoria_api, onboarding_step, updated_at)
            VALUES (?, '', ?, ?, ?, 'COMPLETED', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                industria = excluded.industria,
                industria_exacta = excluded.industria_exacta,
                categoria_api = excluded.categoria_api,
                onboarding_step = 'COMPLETED',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), val, exact_val, cat_val, datetime.utcnow().isoformat())
        )


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
    'STEP_ZONE', 'STEP_INDUSTRY' o 'COMPLETED'.
    """
    if not chat_id:
        return "STEP_ZONE"
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT onboarding_step, zona_preferida, zona_local, zona_pais, industria FROM configuracion_usuario WHERE chat_id = ?",
            (str(chat_id),)
        ).fetchone()
        if not row:
            return "STEP_ZONE"
        keys = row.keys()
        if "onboarding_step" in keys and row["onboarding_step"]:
            st = str(row["onboarding_step"]).strip().upper()
            if st in ("STEP_ZONE", "STEP_INDUSTRY", "COMPLETED"):
                return st
        # Inferencia de respaldo para registros preexistentes
        z_pref = str(row["zona_preferida"] or "").strip()
        z_loc = str(row["zona_local"] or "").strip()
        z_pais = str(row["zona_pais"] or "").strip()
        ind = str(row["industria"] or "").strip()
        has_zone = bool(z_pref or z_loc or z_pais)
        has_ind = bool(ind)
        if has_zone and has_ind:
            return "COMPLETED"
        elif has_zone and not has_ind:
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
    """Borra zona_preferida, zona_local, zona_pais, zonas_json, industria e industria_exacta del usuario en SQLite para reiniciar el onboarding."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, zona_local, zona_pais, zonas_json, industria, industria_exacta, categoria_api, onboarding_step, updated_at)
            VALUES (?, '', '', '', '[]', '', '', 'general', 'STEP_ZONE', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                zona_preferida = '',
                zona_local = '',
                zona_pais = '',
                zonas_json = '[]',
                industria = '',
                industria_exacta = '',
                categoria_api = 'general',
                onboarding_step = 'STEP_ZONE',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), datetime.utcnow().isoformat())
        )


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


