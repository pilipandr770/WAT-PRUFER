# manage.py
# Flask CLI для міграцій: flask db init/migrate/upgrade

from app import create_app
from app.extensions import db
from app.models import User, Company, CompanyOwner, Check, CheckEvent, MonitoringSubscription

app = create_app()

@app.shell_context_processor
def make_context():
    return {
        "db": db,
        "User": User,
        "Company": Company,
        "CompanyOwner": CompanyOwner,
        "Check": Check,
        "CheckEvent": CheckEvent,
        "MonitoringSubscription": MonitoringSubscription,
    }