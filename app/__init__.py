# app/__init__.py
# Створення Flask-додатку, реєстрація розширень і blueprint'ів.

from flask import Flask
from .extensions import db, migrate, login_manager, make_celery
from .config import Config
from .routes.api import api_bp
from .routes.web import web_bp

def create_app(config_object: type[Config] = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    # Розширення
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # User loader for Flask-Login
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Blueprints
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Celery instance на рівні app (створюється при потребі)
    app.celery_app = make_celery(app)

    # Реєструємо Celery таски після створення app
    from .workers import tasks
    tasks._bootstrap_tasks(app)

    @app.route("/health")
    def health():
        return {"status": "ok"}

    return app