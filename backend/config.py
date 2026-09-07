"""Environment-based configuration for the Tracking-project backend.

Runtime mode is explicit. Production configuration fails closed for core
security settings. Optional integrations may be staged, but partial integration
configuration is rejected so the service never runs in an ambiguous state.
"""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

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


def _positive_int(name: str, default: int, *, minimum: int = 1) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


def _boolean(name: str, default: bool = False) -> bool:
    value = os.environ.get(name, str(default)).strip().lower()
    if value not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
        raise RuntimeError(f"{name} must be a boolean")
    return value in {"true", "1", "yes", "on"}


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


def _valid_https_url(url: str) -> bool:
    parsed = urlparse(url)
    return bool(parsed.scheme == "https" and parsed.netloc)


def _production_mongo_error(url: str) -> str | None:
    """Return a fail-closed production Mongo transport/configuration error."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"mongodb", "mongodb+srv"}:
        return "MONGO_URL must use mongodb:// or mongodb+srv://"

    # Strip credentials before evaluating the server list. Production must not
    # point at a loopback database; CI/dev remain free to use localhost.
    hosts = parsed.netloc.rsplit("@", 1)[-1].lower()
    loopback_markers = ("localhost", "127.0.0.1", "[::1]")
    if any(marker in hosts for marker in loopback_markers):
        return "Production MONGO_URL must not use localhost or loopback addresses"

    query = {key.lower(): values for key, values in parse_qs(parsed.query).items()}
    tls_values = [value.lower() for key in ("tls", "ssl") for value in query.get(key, [])]
    if any(value in {"false", "0", "no", "off"} for value in tls_values):
        return "Production MONGO_URL must not disable TLS"

    # mongodb+srv enables TLS by default. Plain mongodb:// does not, so require
    # the deployment URI to opt in explicitly instead of relying on network
    # placement alone.
    if scheme == "mongodb" and not any(value in {"true", "1", "yes", "on"} for value in tls_values):
        return "Production mongodb:// MONGO_URL must explicitly enable TLS (tls=true or ssl=true)"
    return None


class Settings:
    VALID_ENVIRONMENTS = {"development", "test", "preview", "production"}

    APP_ENV: str = _required("APP_ENV").lower()
    MONGO_URL: str = _required("MONGO_URL")
    DB_NAME: str = _required("DB_NAME")

    JWT_SECRET: str = os.environ.get("JWT_SECRET", "").strip()
    JWT_ALGORITHM: str = "HS256"
    OTP_PEPPER: str = os.environ.get("OTP_PEPPER", "").strip()

    OTP_LENGTH: int = _positive_int("OTP_LENGTH", 6, minimum=4)
    OTP_TTL_SECONDS: int = _positive_int("OTP_TTL_SECONDS", 300)
    OTP_MAX_ATTEMPTS: int = _positive_int("OTP_MAX_ATTEMPTS", 5)
    OTP_RESEND_SECONDS: int = _positive_int("OTP_RESEND_SECONDS", 30)
    SESSION_TTL_SECONDS: int = _positive_int("SESSION_TTL_SECONDS", 604800)
    DEBUG_OTP: bool = os.environ.get("DEBUG_OTP", "false").lower() == "true"

    # Order automation can be deployed dark and channels enabled independently.
    AUTOMATION_ENABLED: bool = _boolean("AUTOMATION_ENABLED", False)
    AUTOMATION_VOICE_ENABLED: bool = _boolean("AUTOMATION_VOICE_ENABLED", False)
    AUTOMATION_WHATSAPP_ENABLED: bool = _boolean("AUTOMATION_WHATSAPP_ENABLED", False)
    AUTOMATION_SMS_ENABLED: bool = _boolean("AUTOMATION_SMS_ENABLED", False)
    AUTOMATION_EMAIL_ENABLED: bool = _boolean("AUTOMATION_EMAIL_ENABLED", False)
    AUTOMATION_PUSH_ENABLED: bool = _boolean("AUTOMATION_PUSH_ENABLED", False)
    AUTOMATION_N8N_ENABLED: bool = _boolean("AUTOMATION_N8N_ENABLED", False)
    # Historical replay is opt-in. Routine restarts must not enqueue stale order history.
    AUTOMATION_BACKFILL_ON_STARTUP: bool = _boolean("AUTOMATION_BACKFILL_ON_STARTUP", False)

    # Automation worker heartbeat health thresholds (seconds). The worker is
    # scheduled every minute, so a healthy heartbeat is very recent. These are
    # centralized here instead of scattering magic numbers across the worker,
    # the health monitor and tests.
    AUTOMATION_HEARTBEAT_HEALTHY_SECONDS: int = _positive_int("AUTOMATION_HEARTBEAT_HEALTHY_SECONDS", 180)
    AUTOMATION_HEARTBEAT_WARNING_SECONDS: int = _positive_int("AUTOMATION_HEARTBEAT_WARNING_SECONDS", 300)

    # Plant Staff Authenticator MFA. Optional at process start so production can
    # roll out the code before the Cloud Run secret is attached. MFA endpoints
    # fail closed until a 32+ character key is configured.
    MFA_ENCRYPTION_KEY: str = os.environ.get("MFA_ENCRYPTION_KEY", "").strip()
    MFA_ISSUER: str = os.environ.get("MFA_ISSUER", "TrackMyRMC").strip() or "TrackMyRMC"

    # Plant Staff passkeys/WebAuthn. These are public relying-party identifiers,
    # not secrets. Production defaults are intentionally pinned to TrackMyRMC's
    # canonical HTTPS origin so a deployment cannot silently trust arbitrary
    # hosts. Native Android verification additionally derives the exact app
    # origin from PLAY_SIGNING_SHA256 at request time.
    PASSKEY_RP_ID: str = os.environ.get("PASSKEY_RP_ID", "trackmyrmc.com").strip().lower()
    PASSKEY_RP_NAME: str = os.environ.get("PASSKEY_RP_NAME", "TrackMyRMC").strip() or "TrackMyRMC"
    PASSKEY_WEB_ORIGIN: str = os.environ.get(
        "PASSKEY_WEB_ORIGIN", "https://trackmyrmc.com"
    ).strip().rstrip("/")

    PLAY_REVIEW_ACCESS_ENABLED: bool = os.environ.get(
        "PLAY_REVIEW_ACCESS_ENABLED", "false"
    ).lower() == "true"
    PLAY_REVIEW_ACCESS_CODE: str = os.environ.get("PLAY_REVIEW_ACCESS_CODE", "").strip()

    GOOGLE_OAUTH_CLIENT_ID: str = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "").strip()
    GOOGLE_OAUTH_CLIENT_SECRET: str = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    GOOGLE_OAUTH_REDIRECT_URI: str = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    GOOGLE_OAUTH_APP_REDIRECT_URI: str = os.environ.get(
        "GOOGLE_OAUTH_APP_REDIRECT_URI", "trackmyrmc://auth/google"
    ).strip()

    CORS_ORIGINS: list[str] = _csv("CORS_ORIGINS")

    # Request protections are environment-configurable so operators can tune
    # them without a deployment. Limits are requests per window.
    RATE_LIMIT_WINDOW_SECONDS: int = _positive_int("RATE_LIMIT_WINDOW_SECONDS", 60)
    RATE_LIMIT_AUTH_IP: int = _positive_int("RATE_LIMIT_AUTH_IP", 10)
    RATE_LIMIT_AUTH_ACCOUNT: int = _positive_int("RATE_LIMIT_AUTH_ACCOUNT", 5)
    RATE_LIMIT_PUBLIC: int = _positive_int("RATE_LIMIT_PUBLIC", 60)
    RATE_LIMIT_AUTHENTICATED: int = _positive_int("RATE_LIMIT_AUTHENTICATED", 180)
    RATE_LIMIT_BACKOFF_BASE_SECONDS: int = _positive_int("RATE_LIMIT_BACKOFF_BASE_SECONDS", 2)
    RATE_LIMIT_BACKOFF_MAX_SECONDS: int = _positive_int("RATE_LIMIT_BACKOFF_MAX_SECONDS", 900)
    MAX_AUTH_BODY_BYTES: int = _positive_int("MAX_AUTH_BODY_BYTES", 64 * 1024)
    MAX_UPLOAD_BYTES: int = _positive_int("MAX_UPLOAD_BYTES", 8 * 1024 * 1024)
    MAX_IMAGE_PIXELS: int = _positive_int("MAX_IMAGE_PIXELS", 25_000_000)

    def __init__(self) -> None:
        if self.APP_ENV not in self.VALID_ENVIRONMENTS:
            raise RuntimeError(
                "APP_ENV must be one of: " + ", ".join(sorted(self.VALID_ENVIRONMENTS))
            )

        if self.PLAY_REVIEW_ACCESS_CODE and (
            len(self.PLAY_REVIEW_ACCESS_CODE) != 6 or not self.PLAY_REVIEW_ACCESS_CODE.isdigit()
        ):
            raise RuntimeError("PLAY_REVIEW_ACCESS_CODE must be exactly 6 digits when configured")
        if self.PLAY_REVIEW_ACCESS_ENABLED and not self.PLAY_REVIEW_ACCESS_CODE:
            raise RuntimeError(
                "PLAY_REVIEW_ACCESS_CODE must be configured when reviewer access is enabled"
            )

        if self.MFA_ENCRYPTION_KEY and len(self.MFA_ENCRYPTION_KEY) < 32:
            raise RuntimeError("MFA_ENCRYPTION_KEY must contain at least 32 characters when configured")

        if self.AUTOMATION_HEARTBEAT_WARNING_SECONDS < self.AUTOMATION_HEARTBEAT_HEALTHY_SECONDS:
            raise RuntimeError(
                "AUTOMATION_HEARTBEAT_WARNING_SECONDS must be greater than or equal to "
                "AUTOMATION_HEARTBEAT_HEALTHY_SECONDS"
            )

        if self.is_dev:
            if not self.JWT_SECRET:
                self.JWT_SECRET = "dev-insecure-change-me"
            if not self.OTP_PEPPER:
                self.OTP_PEPPER = "dev-insecure-pepper"
            if not self.MFA_ENCRYPTION_KEY:
                self.MFA_ENCRYPTION_KEY = "dev-insecure-mfa-key-change-me-1234567890"
            if not self.CORS_ORIGINS:
                self.CORS_ORIGINS = ["*"]
            return

        mongo_error = _production_mongo_error(self.MONGO_URL)
        if mongo_error:
            raise RuntimeError(mongo_error)
        if self.DB_NAME.lower() in {"admin", "config", "local"}:
            raise RuntimeError("Production DB_NAME must be an application database, not a MongoDB system database")

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

        if self.PASSKEY_RP_ID != "trackmyrmc.com":
            raise RuntimeError("PASSKEY_RP_ID must be trackmyrmc.com in production")
        if self.PASSKEY_WEB_ORIGIN != "https://trackmyrmc.com":
            raise RuntimeError(
                "PASSKEY_WEB_ORIGIN must be https://trackmyrmc.com in production"
            )

        google_values = (
            self.GOOGLE_OAUTH_CLIENT_ID,
            self.GOOGLE_OAUTH_CLIENT_SECRET,
            self.GOOGLE_OAUTH_REDIRECT_URI,
        )
        google_configured = all(google_values)
        google_partially_configured = any(google_values) and not google_configured
        if google_partially_configured:
            raise RuntimeError(
                "Google OAuth configuration is incomplete; set GOOGLE_OAUTH_CLIENT_ID, "
                "GOOGLE_OAUTH_CLIENT_SECRET and GOOGLE_OAUTH_REDIRECT_URI together"
            )
        if google_configured:
            if not _valid_https_url(self.GOOGLE_OAUTH_REDIRECT_URI):
                raise RuntimeError("GOOGLE_OAUTH_REDIRECT_URI must be an HTTPS URL in production")
            if self.GOOGLE_OAUTH_APP_REDIRECT_URI != "trackmyrmc://auth/google":
                raise RuntimeError(
                    "GOOGLE_OAUTH_APP_REDIRECT_URI must be trackmyrmc://auth/google in production"
                )

        if self.DEBUG_OTP:
            raise RuntimeError("DEBUG_OTP must be false in production")

    @property
    def is_dev(self) -> bool:
        return self.APP_ENV != "production"


settings = Settings()
