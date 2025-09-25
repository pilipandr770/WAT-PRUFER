from ..extensions import db
from ..models import Company, MonitoringSubscription
from ..services.aggregator import apply_results
from ..services.notifier import notify_status_change

from ..adapters.vies_adapter import ViesAdapter
from ..adapters.sanctions_eu_adapter import EUSanctionsAdapter
from ..adapters.sanctions_ofac_adapter import OFACAdapter
from ..adapters.sanctions_uk_adapter import UKSanctionsAdapter
from ..adapters.unternehmensregister_adapter import UnternehmensregisterAdapter
from ..adapters.insolvenz_adapter import InsolvenzAdapter
from ..adapters.whois_denic_adapter import WhoisDenicAdapter
from ..adapters.ssl_labs_adapter import SSLLabsAdapter
from ..adapters.opencorporates_adapter import OpenCorporatesAdapter

def _pre_check_query(company: Company) -> dict:
    name = (company.name or "").strip()
    if name == "---":
        name = ""
    return {
        "vat_number": (company.vat_number or "").strip(),
        "name": name,
        "country": (company.country or "").strip(),
        "address": (company.address or "").strip(),
        "website": (company.website or "").strip(),
    }

def _enrich_company(company: Company, vies_data: dict):
    changed = False
    v_country = vies_data.get("country_code")
    v_addr = vies_data.get("address")
    v_name = vies_data.get("name")

    if v_country and not company.country:
        company.country = v_country; changed = True
    if v_addr and not company.address:
        company.address = v_addr; changed = True
    if v_name and not company.name:
        company.name = v_name; changed = True

    if changed:
        db.session.add(company)
        db.session.commit()

def _maybe_run(adapter, q: dict) -> dict:
    """Безпечний запуск адаптера з мінімально необхідними полями."""
    src = getattr(adapter, "SOURCE", "unknown")
    try:
        # Умови для мінімальних полів
        if src in ("sanctions_eu","sanctions_ofac","sanctions_uk"):
            if not q.get("name"):
                return {"status": "unknown", "data": {}, "source": src, "note": "name required"}
        if src in ("whois","ssl_labs"):
            if not q.get("website"):
                return {"status": "unknown", "data": {}, "source": src, "note": "website required"}
        if src in ("unternehmensregister","insolvenz","opencorporates"):
            if not (q.get("name") or q.get("country") or q.get("address")):
                return {"status": "unknown", "data": {}, "source": src, "note": "insufficient input"}

        return adapter.fetch(q)
    except Exception as e:
        return {"status": "unknown", "data": {"error": str(e), "used_query": q}, "source": src}

def _run_checks(company_id: int):
    company = Company.query.get(company_id)
    if not company:
        return

    q = _pre_check_query(company)
    results = []

    # 1) Спершу VIES
    vies_res = _maybe_run(ViesAdapter(), q)
    results.append(vies_res)

    # 2) Збагачуємо компанію з VIES (якщо щось дали)
    if isinstance(vies_res.get("data"), dict):
        _enrich_company(company, vies_res["data"])

    # Оновити q після збагачення (можливо з’явиться country/address/name)
    q = _pre_check_query(company)

    # 3) Інші адаптери — лише якщо є мінімально потрібні поля
    for adapter in [
        EUSanctionsAdapter(),
        OFACAdapter(),
        UKSanctionsAdapter(),
        UnternehmensregisterAdapter(),
        InsolvenzAdapter(),
        OpenCorporatesAdapter(),
        WhoisDenicAdapter(),
        SSLLabsAdapter(),
    ]:
        results.append(_maybe_run(adapter, q))

    prev = company.current_status or "unknown"
    apply_results(company, results)
    if prev != company.current_status:
        notify_status_change(company.id, prev, company.current_status)

# Expose a module-level function that can be called directly by the smoke runner
def run_full_check_task(company_id: int):
    _run_checks(company_id)
    return {"company_id": company_id, "done": True}


def daily_monitoring_task():
    subs = MonitoringSubscription.query.filter_by(enabled=True).all()
    for s in subs:
        run_full_check_task(s.company_id)
    return {"scheduled": len(subs)}


def _bootstrap_tasks(app):
    """Register Celery tasks on the Flask app's Celery instance.

    app: Flask application created by create_app()
    """
    try:
        celery = app.celery_app
    except Exception:
        return

    @celery.task(name="run_full_check_task")
    def _celery_run_full_check(company_id: int):
        return run_full_check_task(company_id)

    @celery.task(name="daily_monitoring_task")
    def _celery_daily_monitoring():
        return daily_monitoring_task()