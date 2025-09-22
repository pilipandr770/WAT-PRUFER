# app/workers/tasks.py
# Celery таски: основна повна перевірка та щоденний моніторинг

from ..extensions import db
from ..models import Company, MonitoringSubscription
from ..services.aggregator import apply_results
from ..services.notifier import notify_status_change
from flask import current_app

# Адаптери
from ..adapters.vies_adapter import ViesAdapter
from ..adapters.sanctions_eu_adapter import EUSanctionsAdapter
from ..adapters.sanctions_ofac_adapter import OFACAdapter
from ..adapters.sanctions_uk_adapter import UKSanctionsAdapter
from ..adapters.whois_denic_adapter import WhoisDenicAdapter
from ..adapters.ssl_labs_adapter import SSLLabsAdapter
from ..adapters.unternehmensregister_adapter import UnternehmensregisterAdapter
from ..adapters.insolvenz_adapter import InsolvenzAdapter

def _adapters():
    return [
        ViesAdapter(),
        EUSanctionsAdapter(),
        OFACAdapter(),
        UKSanctionsAdapter(),
        UnternehmensregisterAdapter(),
        InsolvenzAdapter(),
        WhoisDenicAdapter(),
        SSLLabsAdapter(),
    ]

# Celery об'єкт беремо з app.celery_app
celery = None

def _ensure_celery():
    global celery
    if celery is None:
        celery = current_app.celery_app
    return celery

def _run_checks(company_id: int):
    company = Company.query.get(company_id)
    if not company:
        return

    q = {
        "vat_number": company.vat_number,
        "name": company.name,
        "country": company.country,
        "address": company.address,
        "website": company.website
    }

    results = []
    for adapter in _adapters():
        try:
            res = adapter.fetch(q)
        except Exception as e:
            res = {"status": "unknown", "data": {"error": str(e)}, "source": getattr(adapter, "SOURCE", "unknown")}
        results.append(res)

    prev = company.current_status or "unknown"
    apply_results(company, results)
    if prev != company.current_status:
        notify_status_change(company.id, prev, company.current_status)

# === Celery tasks ===
def run_full_check_task(company_id: int):
    _run_checks(company_id)
    return {"company_id": company_id, "done": True}

def daily_monitoring_task():
    # Проходимо по підписках і перевіряємо компанії
    subs = MonitoringSubscription.query.filter_by(enabled=True).all()
    for s in subs:
        run_full_check_task.delay(s.company_id)
    return {"scheduled": len(subs)}

def _register_tasks(celery_app):
    global run_full_check_task, daily_monitoring_task
    run_full_check_task = celery_app.task(run_full_check_task)
    daily_monitoring_task = celery_app.task(daily_monitoring_task)

# Під час імпорту модуля — реєструємо таски у контейнері Celery
# (викликається з __init__.py після створення app)
def _bootstrap_tasks(app):
    global celery
    if celery is None:
        celery = app.celery_app
    _register_tasks(celery)