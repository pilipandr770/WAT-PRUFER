# app/workers/tasks.py
# Celery таски: основна повна перевірка та щоденний моніторинг

from ..extensions import db
from ..models import Company, MonitoringSubscription
from ..services.aggregator import apply_results
from ..services.notifier import notify_status_change
from ..services.check_service import persist_check_results
from flask import current_app

# Адаптери
from ..adapters.vies_adapter import ViesAdapter
try:
    from ..adapters.vies_real_adapter import ViesRealAdapter
    VIES_REAL_AVAILABLE = True
except Exception:
    VIES_REAL_AVAILABLE = False
try:
    from ..adapters.opencorporates_adapter import OpenCorporatesAdapter
    OPENCORP_AVAILABLE = True
except Exception:
    OPENCORP_AVAILABLE = False
from ..adapters.sanctions_eu_adapter import EUSanctionsAdapter
from ..adapters.sanctions_ofac_adapter import OFACAdapter
from ..adapters.sanctions_uk_adapter import UKSanctionsAdapter
from ..adapters.whois_denic_adapter import WhoisDenicAdapter
from ..adapters.ssl_labs_adapter import SSLLabsAdapter
from ..adapters.unternehmensregister_adapter import UnternehmensregisterAdapter
from ..adapters.insolvenz_adapter import InsolvenzAdapter

def _adapters():
    adapters = []
    # prefer real VIES if enabled in config
    try:
        from flask import current_app
        if current_app and current_app.config.get("VIES_ENABLED") and VIES_REAL_AVAILABLE:
            adapters.append(ViesRealAdapter())
        else:
            adapters.append(ViesAdapter())
    except Exception:
        adapters.append(ViesAdapter())

    # add Unternehmensregister first
    adapters.append(UnternehmensregisterAdapter())

    # optionally add OpenCorporates if enabled in config
    try:
        from flask import current_app
        if current_app and current_app.config.get("OPENCORP_ENABLED") and OPENCORP_AVAILABLE:
            adapters.append(OpenCorporatesAdapter())
    except Exception:
        pass

    adapters.extend([
        EUSanctionsAdapter(),
        OFACAdapter(),
        UKSanctionsAdapter(),
        InsolvenzAdapter(),
        WhoisDenicAdapter(),
        SSLLabsAdapter(),
    ])
    return adapters

# Celery об'єкт беремо з app.celery_app
celery = None

def _ensure_celery():
    global celery
    if celery is None:
        celery = current_app.celery_app
    return celery

def _run_checks(company_id: int):
    # Use Session.get to avoid SQLAlchemy 2.0 legacy warning
    company = db.session.get(Company, company_id)
    if not company:
        return

    q = {
        "vat_number": company.vat_number,
        "name": company.name,
        "country": company.country,
        "address": company.address,
        "website": company.website,
        "requester_name": company.requester_name,
        "requester_email": company.requester_email,
        "requester_org": company.requester_org,
        "requester": {
            "name": company.requester_name,
            "email": company.requester_email,
            "org": company.requester_org,
        }
    }

    results = {}

    # Run VIES first to enrich company data for downstream adapters
    vies = ViesAdapter()
    try:
        vies_q = q.copy()
        vies_res = vies.fetch(vies_q)
    except Exception as e:
        vies_res = {"status": "unknown", "data": {"error": str(e)}, "source": getattr(vies, "SOURCE", "vies")}
    # record which query was used for this adapter
    try:
        vies_res["used_query"] = vies_q
    except Exception:
        vies_res["used_query"] = q.copy()
    results[vies.SOURCE] = vies_res

    # If VIES returned useful company info, update the Company record so other adapters get the data
    try:
        data = vies_res.get("data") or {}
        changed = False
        # Only update if we have non-empty values
        if data.get("name") and not company.name:
            company.name = data.get("name")
            changed = True
        if data.get("address") and not company.address:
            company.address = data.get("address")
            changed = True
        if data.get("country") and not company.country:
            company.country = data.get("country")
            changed = True
        if data.get("website") and not company.website:
            company.website = data.get("website")
            changed = True
        if changed:
            db.session.add(company)
            db.session.commit()
            # rebuild q from updated company
            q = {
                "vat_number": company.vat_number,
                "name": company.name,
                "country": company.country,
                "address": company.address,
                "website": company.website
            }
    except Exception:
        # If enrichment fails, continue with best-effort
        pass

    # Run the remaining adapters (skip VIES since already executed)
    # Only pass requester fields to adapters that require them (reduce unnecessary sharing)
    REQUESTER_ALLOWED = {"unternehmensregister", "vies", "vies_real"}
    for adapter in _adapters():
        if adapter.SOURCE == vies.SOURCE:
            continue
        try:
            # by default strip requester fields
            if adapter.SOURCE in REQUESTER_ALLOWED:
                adapter_q = q.copy()
            else:
                adapter_q = {k: v for k, v in q.items() if not k.startswith("requester")}
            res = adapter.fetch(adapter_q)
        except Exception as e:
            res = {"status": "unknown", "data": {"error": str(e)}, "source": getattr(adapter, "SOURCE", "unknown")}

        # record which fields were used for this adapter
        try:
            res["used_query"] = adapter_q
        except Exception:
            res["used_query"] = q.copy()

        # store adapter result
        results[adapter.SOURCE] = res

        # If adapter returned company-like data, use it to enrich Company for subsequent adapters
        try:
            data = res.get("data") or {}
            changed = False
            if data.get("name") and not company.name:
                company.name = data.get("name")
                changed = True
            if data.get("address") and not company.address:
                company.address = data.get("address")
                changed = True
            if data.get("country") and not company.country:
                company.country = data.get("country")
                changed = True
            if data.get("website") and not company.website:
                company.website = data.get("website")
                changed = True
            if changed:
                db.session.add(company)
                db.session.commit()
                # update query for next adapters
                q = {
                    "vat_number": company.vat_number,
                    "name": company.name,
                    "country": company.country,
                    "address": company.address,
                    "website": company.website
                }
        except Exception:
            pass

    return results

# === Celery tasks ===
def run_full_check_task(company_id: int):
    # fetch results from adapters
    results = _run_checks(company_id)
    if results:
        check = persist_check_results(company_id, results)
        return {"company_id": company_id, "check_id": check.id, "done": True}
    return {"company_id": company_id, "done": False}

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