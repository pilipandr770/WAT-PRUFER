# app/extensions.py
# Єдине місце для ініціалізації розширень (db/migrate/login/celery)

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from celery import Celery

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

def make_celery(app):
    celery = Celery(app.import_name,
                    broker=app.config["CELERY_BROKER_URL"],
                    backend=app.config["CELERY_RESULT_BACKEND"])
    celery.conf.update(app.config)
    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    celery.Task = ContextTask
    return celery