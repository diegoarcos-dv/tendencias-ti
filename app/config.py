import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables desde .env si existe
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    """Configuración centralizada de la aplicación."""

    APP_ENV: str = os.getenv("APP_ENV", "development")
    APP_PORT: int = int(os.getenv("APP_PORT", "8000"))
    APP_HOST: str = os.getenv("APP_HOST", "0.0.0.0")

    # Rutas
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    BUSINESS_CONTEXT_FILE: Path = BASE_DIR / os.getenv(
        "BUSINESS_CONTEXT_FILE", "data/tendencias.txt"
    )

    # Base de Datos
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/trends.db")

    # Ingesta: Product Hunt
    PRODUCT_HUNT_API_TOKEN: str = os.getenv("PRODUCT_HUNT_API_TOKEN", "")
    PRODUCT_HUNT_CLIENT_ID: str = os.getenv("PRODUCT_HUNT_CLIENT_ID", "")
    PRODUCT_HUNT_CLIENT_SECRET: str = os.getenv("PRODUCT_HUNT_CLIENT_SECRET", "")

    # Ingesta: Reddit
    REDDIT_USER_AGENT: str = os.getenv(
        "REDDIT_USER_AGENT", "CommercialIntelligenceBot/1.0 (by /u/DevTeam)"
    )
    REDDIT_SUBREDDITS: list[str] = [
        s.strip()
        for s in os.getenv(
            "REDDIT_SUBREDDITS", "SaaS,technology,business,entrepreneur,ecommerce"
        ).split(",")
        if s.strip()
    ]

    # Ingesta: Google Trends
    GOOGLE_TRENDS_KEYWORDS: list[str] = [
        k.strip()
        for k in os.getenv(
            "GOOGLE_TRENDS_KEYWORDS",
            "SaaS,ecommerce,agrotech,inteligencia artificial,software B2B",
        ).split(",")
        if k.strip()
    ]

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma:9b")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")
    SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "07:00")
    DEDUPLICATION_WINDOW_DAYS: int = int(os.getenv("DEDUPLICATION_WINDOW_DAYS", "30"))


settings = Settings()
