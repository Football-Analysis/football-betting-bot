import os
from pathlib import Path
from typing import Optional

SECRETS_DIR = Path(os.getenv("DOCKER_SECRETS_DIR", "/run/secrets"))

def _read_secret_file(name: str) -> Optional[str]:
    """
    Reads a Docker Secret from /run/secrets/<name>.
    Strips trailing newline that Docker injects.
    Returns None if not found.
    """
    try:
        p = SECRETS_DIR / name
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return None

def _get(var: str, secret_name: Optional[str] = None, default: Optional[str] = None) -> Optional[str]:
    """
    Resolution order:
      1. VAR_FILE env (explicit file path, works in Compose/K8s)
      2. Plain VAR env (easy in dev)
      3. Secret file (/run/secrets/<secret_name or var.lower()>)
      4. Default
    """
    # 1) explicit file path override
    file_path = os.getenv(f"{var}_FILE")
    if file_path and Path(file_path).exists():
        return Path(file_path).read_text(encoding="utf-8").strip()

    # 2) plain env var
    val = os.getenv(var)
    if val is not None:
        return val

    # 3) docker secret file
    secret = _read_secret_file(secret_name or var.lower())
    if secret is not None:
        return secret

    # 4) fallback default
    return default


class Config:
    # Hosts / URLs
    MONGO_HOST = os.environ.get("MONGO_HOST", "localhost")
    PREDICTION_HOST = os.environ.get("PREDICTION_HOST", "localhost")
    MONGO_URL = f"mongodb://{MONGO_HOST}:27017/"
    PREDICTION_URL = f"http://{PREDICTION_HOST}:8080/prediction"

    # Secrets
    EMAIL_USERNAME = "postandin.notifications@gmail.com"
    EMAIL_PASSWORD = _get("EMAIL_PASSWORD", secret_name="email_password", default="NO PASSWORD SET")
    BETFAIR_API_KEY = _get("BETFAIR_API_KEY", secret_name="betfair_api_key", default=None)
    BETFAIR_USERNAME = _get("BETFAIR_USERNAME", secret_name="betfair_username",  default=None)
    BETFAIR_PASSWORD = _get("BETFAIR_PASSWORD", secret_name="betfair_password", default=None)

    # Betfair
    CERT_LOCATION = os.environ.get("BETFAIR_CERT_DIR", "/home/ubuntu/betfair-cert/")

    # Misc config
    LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "INFO")
    DAY_LIMIT = os.environ.get("DAY_LIMIT", 2)
    THRESHOLD = os.environ.get("THRESHOLD", 0.20)
    BANKROLL_PERCENTAGE = os.environ.get("BANKROLL_PERCENTAGE", 0.01)
