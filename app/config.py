# app/config.py
# Конфігурація: DB URI, Redis/Celery, секрети з .env

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    ENV = os.getenv("FLASK_ENV", "development")

    # БД: за замовчуванням sqlite, можна POSTGRES_URL задавати
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///../instance/company_checker.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis/Celery
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # Developer convenience: run celery tasks eagerly (synchronously) when True
    CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "True") in ("True", "true", "1")

    # Сервісні опції
    APP_NAME = "Company Checker"
    # Enable real VIES SOAP calls when True (requires network and zeep)
    VIES_ENABLED = os.getenv("VIES_ENABLED", "False") in ("True", "true", "1")
    # OpenCorporates
    OPENCORP_ENABLED = os.getenv("OPENCORP_ENABLED", "False") in ("True", "true", "1")
    OPENCORP_API_KEY = os.getenv("OPENCORP_API_KEY", "")
    # Sanctions and external registries
    SANCTIONS_EU_ENABLED = os.getenv("SANCTIONS_EU_ENABLED", "False") in ("True", "true", "1")
    SANCTIONS_OFAC_ENABLED = os.getenv("SANCTIONS_OFAC_ENABLED", "False") in ("True", "true", "1")
    SANCTIONS_UK_ENABLED = os.getenv("SANCTIONS_UK_ENABLED", "False") in ("True", "true", "1")

    # National registries
    UNTERNEHMENSREGISTER_ENABLED = os.getenv("UNTERNEHMENSREGISTER_ENABLED", "False") in ("True", "true", "1")
    INSOLVENZ_ENABLED = os.getenv("INSOLVENZ_ENABLED", "False") in ("True", "true", "1")

    # WHOIS / SSL
    WHOIS_ENABLED = os.getenv("WHOIS_ENABLED", "False") in ("True", "true", "1")
    SSL_LABS_ENABLED = os.getenv("SSL_LABS_ENABLED", "False") in ("True", "true", "1")

    # Sanctions EU specifics
    SANCTIONS_EU_REFRESH = os.getenv("SANCTIONS_EU_REFRESH", "False") in ("True", "true", "1")
    SANCTIONS_EU_FUZZY_THRESHOLD = int(os.getenv("SANCTIONS_EU_FUZZY_THRESHOLD", "92"))

    # HTTP / retries
    EXTERNAL_REQUEST_TIMEOUT = int(os.getenv("EXTERNAL_REQUEST_TIMEOUT", "30"))
    EXTERNAL_REQUEST_RETRIES = int(os.getenv("EXTERNAL_REQUEST_RETRIES", "2"))
    CACHE_DIR = os.getenv("CACHE_DIR", os.path.join(os.path.dirname(__file__), "data"))
    # Optional proxy settings (can be set via environment variables HTTP_PROXY/HTTPS_PROXY)
    HTTP_PROXY = os.getenv('HTTP_PROXY', '')
    HTTPS_PROXY = os.getenv('HTTPS_PROXY', '')