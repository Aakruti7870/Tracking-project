"""Environment-based configuration for TrackMyRMC backend."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


class Settings:
    # Mongo
    MONGO_URL: str = os.environ["MONGO_URL"]
    DB_NAME: str = os.environ["DB_NAME"]

    # Auth / OTP
    JWT_SECRET: str = os.environ.get("JWT_SECRET", "dev-insecure-change-me")
    JWT_ALGORITHM: str = "HS256"
    OTP_PEPPER: str = os.environ.get("OTP_PEPPER", "dev-insecure-pepper")

    OTP_LENGTH: int = int(os.environ.get("OTP_LENGTH", 6))
    OTP_TTL_SECONDS: int = int(os.environ.get("OTP_TTL_SECONDS", 300))
    OTP_MAX_ATTEMPTS: int = int(os.environ.get("OTP_MAX_ATTEMPTS", 5))
    OTP_RESEND_SECONDS: int = int(os.environ.get("OTP_RESEND_SECONDS", 30))
    SESSION_TTL_SECONDS: int = int(os.environ.get("SESSION_TTL_SECONDS", 604800))

    # Environment
    APP_ENV: str = os.environ.get("APP_ENV", "development")
    DEBUG_OTP: bool = os.environ.get("DEBUG_OTP", "true").lower() == "true"

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV != "production"


settings = Settings()
