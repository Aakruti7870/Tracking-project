"""Runtime configuration must never silently infer development mode."""
import os
from pathlib import Path
import subprocess
import sys


def _run(env_updates: dict[str, str | None]):
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(
        {
            "MONGO_URL": "mongodb+srv://unit:unit@example.mongodb.net",
            "DB_NAME": "runtime_config_test",
            "JWT_SECRET": "unit-production-secret-long-enough-1234567890",
            "OTP_PEPPER": "unit-production-pepper-long-enough-1234567890",
            "DEBUG_OTP": "false",
            "CORS_ORIGINS": "https://trackmyrmc.com",
        }
    )
    for key, value in env_updates.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return subprocess.run(
        [sys.executable, "-c", "import config"],
        cwd=backend,
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_app_env_is_required():
    result = _run({"APP_ENV": None})
    assert result.returncode != 0
    assert "APP_ENV" in (result.stdout + result.stderr)


def test_invalid_app_env_is_rejected():
    result = _run({"APP_ENV": "prod"})
    assert result.returncode != 0
    assert "APP_ENV must be one of" in (result.stdout + result.stderr)


def test_production_cors_requires_https_origin_only():
    result = _run({"APP_ENV": "production", "CORS_ORIGINS": "https://trackmyrmc.com/path"})
    assert result.returncode != 0
    assert "CORS_ORIGINS" in (result.stdout + result.stderr)


def test_production_mongo_rejects_loopback():
    result = _run({"APP_ENV": "production", "MONGO_URL": "mongodb://127.0.0.1:27017/?tls=true"})
    assert result.returncode != 0
    assert "loopback" in (result.stdout + result.stderr)


def test_production_mongo_rejects_plaintext_transport():
    result = _run({"APP_ENV": "production", "MONGO_URL": "mongodb://db.example.test:27017"})
    assert result.returncode != 0
    assert "enable TLS" in (result.stdout + result.stderr)


def test_production_mongo_rejects_explicit_tls_disable():
    result = _run({"APP_ENV": "production", "MONGO_URL": "mongodb+srv://unit:unit@example.mongodb.net/?tls=false"})
    assert result.returncode != 0
    assert "must not disable TLS" in (result.stdout + result.stderr)


def test_production_mongo_rejects_system_database_name():
    result = _run({"APP_ENV": "production", "DB_NAME": "admin"})
    assert result.returncode != 0
    assert "application database" in (result.stdout + result.stderr)


def test_secure_production_config_imports():
    result = _run({"APP_ENV": "production"})
    assert result.returncode == 0, result.stdout + result.stderr
