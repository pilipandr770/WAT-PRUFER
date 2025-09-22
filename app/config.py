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
        "sqlite:///company_checker.db"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis/Celery
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)

    # Сервісні опції
    APP_NAME = "Company Checker"