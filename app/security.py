"""Capa de Seguridad de APIs (api-security-best-practices).

Responsabilidades:
1. Verificación segura en tiempo constante de API Keys para endpoints administrativos.
2. Validación de tokens secretos de Webhook de Telegram.
3. Desinfección y neutralización de Prompt Injection indirecto en datos externos de la web.
4. Prevención de fugas de datos (Data Leak Prevention / Redaction) de tokens, IPs privadas y rutas internas.
"""

import hmac
import re
import logging
from typing import Optional
from fastapi import Header, HTTPException, status
from app.config import settings

logger = logging.getLogger(__name__)

# Cabeceras estándar de autenticación
API_KEY_HEADER_NAME = "X-API-KEY"
TELEGRAM_SECRET_HEADER_NAME = "X-Telegram-Bot-Api-Secret-Token"

# Patrones sensibles para prevención de fugas de datos (DLP / Output Sanitization)
# 1. Tokens de bot de Telegram: 123456789:ABCdefGhIjkLmNoPqRsTuVwXyZ
_TELEGRAM_TOKEN_PATTERN = re.compile(r"\b\d{8,10}:[A-Za-z0-9_-]{35}\b")
# 2. Direcciones IP privadas (RFC 1918): 10.x.x.x, 192.168.x.x, 172.16-31.x.x
_PRIVATE_IP_PATTERN = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
# 3. Rutas absolutas del sistema de archivos de Windows o Linux
_INTERNAL_PATH_PATTERN = re.compile(r"(?:[A-Za-z]:\\[\w\s\\.-]+|/(?:apps|home|root|var|etc)/[\w\s/.-]+)")

# Patrones de inyección de prompts indirecta en feeds o APIs de terceros
_PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions\b"),
    re.compile(r"(?i)\bolvida\s+(?:todas\s+las\s+)?instrucciones\s+(?:previas|anteriores)\b"),
    re.compile(r"(?i)\byou\s+are\s+now\s+(?:a|an)\b"),
    re.compile(r"(?i)\bahora\s+eres\s+(?:un|una)\b"),
    re.compile(r"(?i)\bsystem\s+prompt\b"),
    re.compile(r"(?i)\breveal\s+(?:the\s+)?(?:secret|token|password|key)\b"),
    re.compile(r"(?i)\bmuestra\s+(?:el\s+)?(?:secreto|token|contraseña|clave)\b"),
    re.compile(r"(?i)\bdo\s+anything\s+now\b"),
]


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias=API_KEY_HEADER_NAME)
) -> bool:
    """Valida la API Key de autorización usando comparación en tiempo constante (timing attack protection).
    
    Aplica api-security-best-practices:
    - Retorna 401 genérico sin filtrar el motivo exacto o el token esperado.
    - Utiliza hmac.compare_digest para evitar ataques basados en medición de tiempos de respuesta.
    """
    configured_key = settings.API_SECRET_KEY
    if not configured_key:
        logger.error("[Seguridad API] API_SECRET_KEY no configurada en el entorno.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno de configuración de seguridad."
        )

    if not x_api_key:
        logger.warning(f"[Seguridad API] Intento de acceso sin cabecera {API_KEY_HEADER_NAME}.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: Cabecera de autenticación requerida.",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME}
        )

    # Comparación segura en tiempo constante
    is_valid = hmac.compare_digest(x_api_key.strip(), configured_key.strip())
    if not is_valid:
        logger.warning(f"[Seguridad API] Intento de acceso denegado con clave inválida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: Clave de acceso inválida.",
            headers={"WWW-Authenticate": API_KEY_HEADER_NAME}
        )

    return True


def verify_telegram_webhook_secret(
    x_telegram_secret: Optional[str] = Header(None, alias=TELEGRAM_SECRET_HEADER_NAME)
) -> bool:
    """Valida el token secreto que Telegram envía en el webhook si está configurado."""
    configured_secret = settings.TELEGRAM_WEBHOOK_SECRET
    if not configured_secret:
        # Si no se ha configurado un secreto para webhook, permitir solo en desarrollo
        if settings.APP_ENV == "production":
            logger.warning("[Seguridad Webhook] TELEGRAM_WEBHOOK_SECRET no configurada en producción.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Acceso denegado: Webhook deshabilitado o no configurado."
            )
        return True

    if not x_telegram_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token secreto de webhook faltante."
        )

    if not hmac.compare_digest(x_telegram_secret.strip(), configured_secret.strip()):
        logger.warning("[Seguridad Webhook] Token secreto de Telegram inválido.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token secreto de webhook inválido."
        )

    return True


def sanitize_external_text(text: Optional[str], max_len: int = 1500) -> str:
    """Sanitiza texto proveniente de APIs de terceros (Product Hunt, Reddit, RSS)
    antes de ser procesado por el LLM para evitar ataques de Prompt Injection.
    """
    if not text or not isinstance(text, str):
        return ""

    sanitized = text.strip()

    # 1. Truncar longitud excesiva
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]

    # 2. Desactivar patrones conocidos de prompt injection
    for pattern in _PROMPT_INJECTION_PATTERNS:
        if pattern.search(sanitized):
            logger.warning(f"[Seguridad LLM] Neutralizado patrón sospechoso de prompt injection en contenido externo.")
            sanitized = pattern.sub("[CONTENIDO RESTRINGIDO POR SEGURIDAD]", sanitized)

    # 3. Remover caracteres de control y delimitadores peligrosos de formato
    sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", sanitized)
    
    return sanitized


def redact_sensitive_data(text: str) -> str:
    """Ofusca tokens de Telegram, IPs privadas y rutas absolutas antes de emitir
    logs públicos o mensajes que el usuario final pueda leer.
    """
    if not text or not isinstance(text, str):
        return ""

    # Redactar tokens de Telegram
    redacted = _TELEGRAM_TOKEN_PATTERN.sub("[TELEGRAM_TOKEN_REDACTED]", text)
    # Redactar IPs de red privada
    redacted = _PRIVATE_IP_PATTERN.sub("[IP_PRIVADA_REDACTADA]", redacted)
    # Redactar rutas internas del servidor
    redacted = _INTERNAL_PATH_PATTERN.sub("[RUTA_INTERNA_REDACTADA]", redacted)

    return redacted
