"""Environment-based configuration for TrackMyRMC backend.

Production configuration fails closed: secrets and allowed origins must be
provided explicitly instead of silently falling back to development defaults.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


def _csv(name: str) -> list[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


class Settings:
    # Environment first so all later defaults can be environment-aware.
    APP_ENV: str = os.environ.get("APP_ENV", "development").strip().lower()

    # Mongo
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]

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
        if self.is_dev:
            # Keep local/preview development usable without weakening production.
            if not self.JWT_SECRET:
                self.JWT_SECRET = "dev-insecure-change-me"
            if not self.OTP_PEPPER:
                self.OTP_PEPPER = "dev-insecure-pepper"
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["*"]
            return

        missing = []
        if not self.JWT_SECRET or self.JWT_SECRET.startswith("dev-insecure"):
            missing.append("JWT_SECRET")
        if not self.OTP_PEPPER or self.OTP_PEPPER.startswith("dev-insecure"):
            missing.append("OTP_PEPPER")
        if missing:
            raise RuntimeError(
                "Production security configuration missing/unsafe: " + ", ".join(missing)
            )
        if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
            raise RuntimeError(
                "Production CORS_ORIGINS must contain explicit trusted origins and must not contain '*'"
            )
        if self.DEBUG_OTP:
            raise RuntimeError("DEBUG_OTP must be false in production")

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV != "production"


settings = Settings()
