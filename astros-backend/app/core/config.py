import os
from pathlib import Path

from dotenv import load_dotenv

# Locate the .env file in the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is missing. Check your .env file."
    )

# Environmental & Visibility Intelligence configurations
OPEN_METEO_BASE_URL = os.getenv(
    "OPEN_METEO_BASE_URL", "https://api.open-meteo.com/v1/forecast"
)
WEATHER_REQUEST_TIMEOUT_SECONDS = float(
    os.getenv("WEATHER_REQUEST_TIMEOUT_SECONDS", "10.0")
)
WEATHER_CACHE_TTL_SECONDS = int(
    os.getenv("WEATHER_CACHE_TTL_SECONDS", "1800")
)
LIGHT_POLLUTION_DATA_PATH = os.getenv("LIGHT_POLLUTION_DATA_PATH") or None

# DarkSkySites Light Pollution API
DARKSKYSITES_API_KEY = os.getenv("DARKSKYSITES_API_KEY") or None
DARKSKYSITES_BASE_URL = os.getenv(
    "DARKSKYSITES_BASE_URL", "https://darkskysites.com/api/sqm"
)
DARKSKYSITES_TIMEOUT_SECONDS = float(
    os.getenv("DARKSKYSITES_TIMEOUT_SECONDS", "10.0")
)
DARKSKYSITES_CACHE_TTL_SECONDS = int(
    os.getenv("DARKSKYSITES_CACHE_TTL_SECONDS", "86400")  # 24 h — static data
)

# API documentation: set to "false" to disable /docs and /redoc in production.
ENABLE_API_DOCS = os.getenv("ENABLE_API_DOCS", "true").lower() not in ("false", "0", "no")

# CORS: comma-separated list of allowed origins.
# Example: "https://app.example.com,https://www.example.com"
# Leave empty in development (CORS disabled = no cross-origin access).
CORS_ALLOWED_ORIGINS_RAW = os.getenv("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOWED_ORIGINS: list[str] = [
    o.strip() for o in CORS_ALLOWED_ORIGINS_RAW.split(",") if o.strip()
]

# --- JWT Authentication Configuration ---

# Algorithms accepted for the JWT_ALGORITHM variable.
SUPPORTED_JWT_ALGORITHMS: frozenset[str] = frozenset({"HS256", "HS384", "HS512"})

JWT_SECRET_KEY: str | None = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "20"))
REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ENABLE_PUBLIC_REGISTRATION: bool = os.getenv(
    "ENABLE_PUBLIC_REGISTRATION", "true"
).lower() not in ("false", "0", "no")

# Deployment environment — controls strictness of JWT secret validation.
ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()

# Validate JWT algorithm at startup.
if JWT_ALGORITHM not in SUPPORTED_JWT_ALGORITHMS:
    raise RuntimeError(
        f"JWT_ALGORITHM '{JWT_ALGORITHM}' is not supported. "
        f"Supported algorithms: {sorted(SUPPORTED_JWT_ALGORITHMS)}"
    )

# Validate token lifetimes at startup.
if ACCESS_TOKEN_EXPIRE_MINUTES <= 0:
    raise RuntimeError(
        "ACCESS_TOKEN_EXPIRE_MINUTES must be a positive integer."
    )
if REFRESH_TOKEN_EXPIRE_DAYS <= 0:
    raise RuntimeError(
        "REFRESH_TOKEN_EXPIRE_DAYS must be a positive integer."
    )

# Known placeholder values that must never be used as a real secret.
_KNOWN_JWT_PLACEHOLDERS: frozenset[str] = frozenset({
    "replace_with_a_secure_random_secret",
    "your-secret-key",
    "changeme",
    "secret",
    "jwt_secret",
})


def _validate_jwt_secret(secret: str | None, *, require: bool) -> None:
    """Validate JWT secret material.

    Always rejects known placeholder strings and secrets shorter than 32 bytes.
    In production (``require=True``) a missing secret is also rejected.

    The secret value is never included in any error message.
    """
    if secret is None or not secret.strip():
        if require:
            raise RuntimeError(
                "JWT_SECRET_KEY is required in production. "
                "Set a cryptographically random secret of at least 32 bytes. "
                "Do not use a placeholder value."
            )
        return

    stripped = secret.strip()

    if stripped.lower() in _KNOWN_JWT_PLACEHOLDERS:
        raise RuntimeError(
            "JWT_SECRET_KEY contains a known placeholder value. "
            "Generate a cryptographically random secret of at least 32 bytes "
            "and set it in your .env file."
        )

    if len(stripped.encode()) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY is too short. "
            "Provide at least 32 bytes of cryptographically random secret material."
        )


_validate_jwt_secret(JWT_SECRET_KEY, require=(ENVIRONMENT == "production"))

