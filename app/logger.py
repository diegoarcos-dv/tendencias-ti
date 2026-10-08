"""Módulo centralizado de logging para depuración y observabilidad del sistema."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.config import settings

_LOGGING_INITIALIZED = False


def setup_logging(level: int = logging.INFO) -> None:
    """Configura el logging unificado con salida a consola y archivo rotativo (app.log).

    - Consola y archivo con formato limpio y marcas de tiempo precisas.
    - Archivo rotativo en data/app.log (máx 5MB, 3 copias de seguridad).
    - Silencia peticiones repetitivas de httpx/httpcore para no inundar la consola durante el long polling.
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return

    log_dir: Path = settings.DATA_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file: Path = log_dir / "app.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Handler de Consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # 2. Handler de Archivo con rotación
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Evitar handlers duplicados si se llama múltiples veces
    root_logger.handlers.clear()
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    # Silenciar librerías externas verbosas
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("apscheduler.executors.default").setLevel(logging.WARNING)

    _LOGGING_INITIALIZED = True
    logging.getLogger("app.logger").info(f"[Logger] Sistema de logs inicializado. Guardando en: {log_file}")


# Instancia de conveniencia para importación directa: from app.logger import logger
logger = logging.getLogger("app")
