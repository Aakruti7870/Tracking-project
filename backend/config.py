"""Environment-based configuration for the Tracking-project backend.

Runtime mode is explicit. Production configuration fails closed: secrets and
trusted origins must be provided instead of silently falling back to development
settings.
"""
import os
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


def _csv(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def _valid_production_origin(origin: str) -> bool:
    """Production CORS entries must be explicit HTTPS origins, not URLs/paths."""
    if "*" in origin:
        return False
    parsed = urlparse(origin)
    return bool(
        parsed.scheme == "https"
        and parsed.netloc
        and not parsed.path.rstrip("/")
        and not parsed.params
        and not parsed.query
        and not parsed.fragment
    )


class Settings:
    VALID_ENVIRONMENTS = {"development", "test", "preview", "production"}

    # Never infer development mode. A deployment that forgets APP_ENV must fail.
    APP_ENV: str = _required("APP_ENV").lower()

    # Mongo
    MONGO_URL: str = _required("MONGO_URL")
    DB_NAME: str = _required("DB_NAME")

    # Auth / OTP
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "").strip()
    JWT_ALGORITHM: str = "HS256"
    OTP_PEPPER: str = os.environ.get("OTP_PEPPER", "").strip()

    OTP_LENGTH: int = int(os.environ.get("OTP_LENGTH", 6))
    OTP_TTL_SECONDS: int = int(os.environ.get("OTP_TTL_SECONDS", 300))
    OTP_MAX_ATTEMPTS: int = int(os.environ.get("OTP_MAX_ATTEMPTS", 5))
    OTP_RESEND_SECONDS: int = int(os.environ.get("OTP_RESEND_SECONDS", 30))
    SESSION_TTL_SECONDS: int = int(os.environ.get("SESSION_TTL_SECONDS", 604800))
    DEBUG_OTP: bool = os.environ.get("DEBUG_OTP", "false").lower() == "true"

    # HTTP security
    CORS_ORIGINS: list[str] = _csv("CORS_ORIGINS")

    def __init__(self) -> None:
        if self.APP_ENV not in self.VALID_ENVIRONMENTS:
            raise RuntimeError(
                "APP_ENV must be one of: " + ", ".join(sorted(self.VALID_ENVIRONMENTS))
            )

        if self.is_dev:
            # Keep local/test/preview usable without weakening production.
            if not self.JWT_SECRET:
                self.JWT_SECRET = "dev-insecure-change-me"
            if not self.OTP_PEPPER:
                self.OTP_PEPPER = "dev-insecure-pepper"
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["*"]
            return

        missing = []
        if len(self.JWT_SECRET) < 32 or self.JWT_SECRET.startswith("dev-insecure"):
            missing.append("JWT_SECRET")
        if len(self.OTP_PEPPER) < 32 or self.OTP_PEPPER.startswith("dev-insecure"):
            missing.append("OTP_PEPPER")
        if missing:
            raise RuntimeError(
                "Production security configuration missing/unsafe: " + ", ".join(missing)
            )
        if not self.CORS_ORIGINS or not all(
            _valid_production_origin(origin) for origin in self.CORS_ORIGINS
        ):
            raise RuntimeError(
                "Production CORS_ORIGINS must contain explicit HTTPS origins only; wildcards, paths and query strings are forbidden"
            )
        if self.DEBUG_OTP:
            raise RuntimeError("DEBUG_OTP must be false in production")

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV != "production"


settings = Settings()
