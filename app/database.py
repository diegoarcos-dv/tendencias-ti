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

            CREATE INDEX IF NOT EXISTS idx_guardadas_url_hash
                ON tendencias_guardadas (url_hash);
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


def mark_as_favorite(trend_id: int, message_id: Optional[int] = None) -> bool:
    """Copia una entrada del historial a tendencias_guardadas como favorito, asociando el message_id si existe."""
    with _get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM historial_envios WHERE id = ?", (trend_id,)
        ).fetchone()
        if not row:
            return False
        conn.execute(
            """
            INSERT INTO tendencias_guardadas
                (url, url_hash, title, source, category, score, llm_analysis, saved_at, is_favorite, message_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(url_hash) DO UPDATE SET
                message_id = COALESCE(excluded.message_id, tendencias_guardadas.message_id),
                saved_at = excluded.saved_at
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


def get_favorites() -> List[Dict[str, Any]]:
    """Obtiene la lista de tendencias marcadas como favoritas."""
    with _get_connection() as conn:
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
