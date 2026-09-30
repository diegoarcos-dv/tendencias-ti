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
                url            TEXT    NOT NULL,
                url_hash       TEXT    NOT NULL UNIQUE,
                title          TEXT    NOT NULL,
                source         TEXT    NOT NULL DEFAULT '',
                category       TEXT    NOT NULL DEFAULT '',
                score          REAL    NOT NULL DEFAULT 0.0,
                llm_analysis   TEXT    DEFAULT NULL,
                saved_at       TEXT    NOT NULL,
                is_favorite    INTEGER NOT NULL DEFAULT 1,
                message_id     INTEGER DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS configuracion_usuario (
                chat_id         TEXT PRIMARY KEY,
                zona_preferida  TEXT NOT NULL DEFAULT 'Global',
                industria       TEXT NOT NULL DEFAULT 'TI & Software B2B',
                updated_at      TEXT NOT NULL
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
        if "industria" not in cfg_cols and cfg_cols:
            conn.execute("ALTER TABLE configuracion_usuario ADD COLUMN industria TEXT NOT NULL DEFAULT 'TI & Software B2B'")


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


def mark_as_favorite(trend_id: int, message_id: Optional[int] = None, user_id: Optional[Any] = None) -> bool:
    """Copia una entrada del historial a tendencias_guardadas como favorito, asociando el message_id y user_id si existen."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM historial_envios WHERE id = ?", (trend_id,)
        ).fetchone()
        if not row:
            return False

        cols = {col[1] for col in conn.execute("PRAGMA table_info(tendencias_guardadas)").fetchall()}
        has_uid = "user_id" in cols

        if has_uid:
            conn.execute(
                """
                INSERT INTO tendencias_guardadas
                    (url, url_hash, title, source, category, score, llm_analysis, saved_at, is_favorite, message_id, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    message_id = COALESCE(excluded.message_id, tendencias_guardadas.message_id),
                    user_id = COALESCE(excluded.user_id, tendencias_guardadas.user_id),
                    saved_at = excluded.saved_at,
                    is_favorite = 1
                """,
                (
                    row["url"],
                    row["url_hash"],
                    row["title"],
                    row["source"],
                    row["category"],
                    row["score"],
                    row["card_data"] if "card_data" in row.keys() else None,
                    datetime.utcnow().isoformat(),
                    message_id,
                    str(user_id) if user_id is not None else None,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO tendencias_guardadas
                    (url, url_hash, title, source, category, score, llm_analysis, saved_at, is_favorite, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                ON CONFLICT(url_hash) DO UPDATE SET
                    message_id = COALESCE(excluded.message_id, tendencias_guardadas.message_id),
                    saved_at = excluded.saved_at,
                    is_favorite = 1
                """,
                (
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


def remove_favorite(user_id: Any, trend_id: int) -> bool:
    """Elimina una tendencia de favoritos en tendencias_guardadas usando user_id y trend_id."""
    with _get_connection() as conn:
        cols = {col[1] for col in conn.execute("PRAGMA table_info(tendencias_guardadas)").fetchall()}
        has_uid = "user_id" in cols

        if has_uid and user_id is not None:
            cursor = conn.execute(
                """
                DELETE FROM tendencias_guardadas
                WHERE (id = ? OR url_hash IN (SELECT url_hash FROM historial_envios WHERE id = ?))
                  AND (user_id = ? OR user_id IS NULL)
                """,
                (trend_id, trend_id, str(user_id))
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM tendencias_guardadas
                WHERE id = ? OR url_hash IN (SELECT url_hash FROM historial_envios WHERE id = ?)
                """,
                (trend_id, trend_id)
            )
        return cursor.rowcount > 0


def get_favorites(user_id: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Obtiene la lista de tendencias marcadas como favoritas (opcionalmente filtradas por user_id)."""
    with _get_connection() as conn:
        cols = {col[1] for col in conn.execute("PRAGMA table_info(tendencias_guardadas)").fetchall()}
        if "user_id" in cols and user_id is not None:
            rows = conn.execute(
                "SELECT * FROM tendencias_guardadas WHERE is_favorite = 1 AND (user_id = ? OR user_id IS NULL) ORDER BY saved_at DESC",
                (str(user_id),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tendencias_guardadas WHERE is_favorite = 1 ORDER BY saved_at DESC"
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


def set_user_zone(chat_id: str, zone: Optional[str]) -> None:
    """Guarda o actualiza la zona geográfica preferida del usuario en SQLite."""
    val = str(zone).strip() if zone else ""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, industria, updated_at)
            VALUES (?, ?, '', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                zona_preferida = excluded.zona_preferida,
                updated_at = excluded.updated_at
            """,
            (str(chat_id), val, datetime.utcnow().isoformat())
        )


def get_user_zone(chat_id: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Obtiene la zona geográfica preferida del usuario (None si está vacía)."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT zona_preferida FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row and row["zona_preferida"] and str(row["zona_preferida"]).strip():
                return str(row["zona_preferida"]).strip()
            return default

        # Si no se especificó chat_id o no existe aún, tomar la última guardada no vacía
        row = conn.execute(
            "SELECT zona_preferida FROM configuracion_usuario WHERE zona_preferida IS NOT NULL AND zona_preferida != '' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row and row["zona_preferida"] and str(row["zona_preferida"]).strip():
            return str(row["zona_preferida"]).strip()

        return default or "Global"


def set_user_industry(chat_id: str, industry: Optional[str]) -> None:
    """Guarda o actualiza la industria preferida del usuario en SQLite."""
    val = str(industry).strip() if industry else ""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, industria, updated_at)
            VALUES (?, '', ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                industria = excluded.industria,
                updated_at = excluded.updated_at
            """,
            (str(chat_id), val, datetime.utcnow().isoformat())
        )


def get_user_industry(chat_id: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """Obtiene la industria preferida del usuario (None si está vacía)."""
    with _get_connection() as conn:
        if chat_id:
            row = conn.execute(
                "SELECT industria FROM configuracion_usuario WHERE chat_id = ?",
                (str(chat_id),)
            ).fetchone()
            if row and row["industria"] and str(row["industria"]).strip():
                return str(row["industria"]).strip()
            return default

        row = conn.execute(
            "SELECT industria FROM configuracion_usuario WHERE industria IS NOT NULL AND industria != '' ORDER BY updated_at DESC LIMIT 1"
        ).fetchone()
        if row and row["industria"] and str(row["industria"]).strip():
            return str(row["industria"]).strip()

        return default or "TI & Software B2B"


def reset_user_config(chat_id: str) -> None:
    """Borra zona_preferida e industria del usuario en SQLite para reiniciar el onboarding."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_usuario (chat_id, zona_preferida, industria, updated_at)
            VALUES (?, '', '', ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                zona_preferida = '',
                industria = '',
                updated_at = excluded.updated_at
            """,
            (str(chat_id), datetime.utcnow().isoformat())
        )


def get_all_configured_users() -> List[Dict[str, Any]]:
    """Consulta en SQLite a todos los usuarios con perfil completo (zona e industria no vacías)."""
    with _get_connection() as conn:
        rows = conn.execute(
            """
            SELECT chat_id, zona_preferida, industria, updated_at
            FROM configuracion_usuario
            WHERE zona_preferida IS NOT NULL AND TRIM(zona_preferida) != ''
              AND industria IS NOT NULL AND TRIM(industria) != ''
            ORDER BY updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]


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

