"""Celery tasks and adapter orchestration for company checks.

Provides a pipeline that runs VIES first (to enrich company data) and then the
other adapters. The application expects this module to expose a
`_bootstrap_tasks(app)` function that will register Celery tasks when the app
is created; for local use the module also exposes `run_full_check_task`.
"""

from flask import current_app
from ..extensions import db
from ..models import Company, MonitoringSubscription
from ..services.aggregator import apply_results
from ..services.notifier import notify_status_change
import logging

logger = logging.getLogger(__name__)

# Adapters — we intentionally use a single robust VIES adapter implementation
from ..adapters.vies_adapter import ViesAdapter
from ..adapters.sanctions_eu_adapter import EUSanctionsAdapter
from ..adapters.sanctions_ofac_adapter import OFACAdapter
from ..adapters.sanctions_uk_adapter import UKSanctionsAdapter
from ..adapters.unternehmensregister_adapter import UnternehmensregisterAdapter
from ..adapters.insolvenz_adapter import InsolvenzAdapter
from ..adapters.whois_denic_adapter import WhoisDenicAdapter
from ..adapters.ssl_labs_adapter import SSLLabsAdapter
from ..adapters.opencorporates_adapter import OpenCorporatesAdapter


def _adapters():
    return [
        ViesAdapter(),
        EUSanctionsAdapter(),
        OFACAdapter(),
        UKSanctionsAdapter(),
        UnternehmensregisterAdapter(),
        InsolvenzAdapter(),
        OpenCorporatesAdapter(),
        WhoisDenicAdapter(),
        SSLLabsAdapter(),
    ]


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


def _enrich_company_from_vies(company: Company, vies_data: dict):
    v_name = vies_data.get("name")
    v_addr = vies_data.get("address")
    v_country = vies_data.get("country_code")

    changed = False
    if v_country and not (company.country and company.country.strip()):
        company.country = v_country
        changed = True
    if v_addr and not (company.address and company.address.strip()):
        company.address = v_addr
        changed = True
    if v_name and not (company.name and company.name.strip() and company.name.strip() != "---"):
        company.name = v_name
        changed = True

    if changed:
        db.session.add(company)
        db.session.commit()


def _run_checks(company_id: int):
    c = db.session.get(Company, company_id)
    if not c:
        return

    q = _pre_check_query(c)
    results = []
    vies_result = None

    for adapter in _adapters():
        try:
            res = adapter.fetch(q)
        except Exception as e:
            logger.exception("Adapter %s failed", getattr(adapter, "SOURCE", type(adapter)))
            res = {"status": "unknown", "data": {"error": str(e), "used_query": q}, "source": getattr(adapter, "SOURCE", "unknown")}
        results.append(res)

        if getattr(adapter, "SOURCE", "") == "vies" and isinstance(res.get("data"), dict):
            vies_result = res

    if vies_result and isinstance(vies_result.get("data"), dict):
        _enrich_company_from_vies(c, vies_result["data"])

    prev = c.current_status or "unknown"
    apply_results(c, results)
    if prev != c.current_status:
        notify_status_change(c.id, prev, c.current_status)


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
# TEMPORARY OVERRIDE: force-disable the optional real adapter until network/proxy issues are resolved
# This ensures we only use the robust in-repo ViesAdapter which ignores env proxies.
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

# app/workers/tasks.py
# Celery таски: основна повна перевірка та щоденний моніторинг

from flask import current_app
from ..extensions import db
from ..models import Company, MonitoringSubscription
from ..services.aggregator import apply_results
from ..services.notifier import notify_status_change

# Адаптери — використовуємо тільки один VIES адаптер і решту перевірок
from ..adapters.vies_adapter import ViesAdapter
from ..adapters.sanctions_eu_adapter import EUSanctionsAdapter
from ..adapters.sanctions_ofac_adapter import OFACAdapter
from ..adapters.sanctions_uk_adapter import UKSanctionsAdapter
from ..adapters.unternehmensregister_adapter import UnternehmensregisterAdapter
from ..adapters.insolvenz_adapter import InsolvenzAdapter
from ..adapters.whois_denic_adapter import WhoisDenicAdapter
from ..adapters.ssl_labs_adapter import SSLLabsAdapter
from ..adapters.opencorporates_adapter import OpenCorporatesAdapter


def _adapters():
    # Порядок важливий: спочатку VIES (щоб підтягнути країну/адресу),
    # далі санкції (потребують name), потім реєстри й техперевірки.
    return [
        ViesAdapter(),
        EUSanctionsAdapter(),
        OFACAdapter(),
        UKSanctionsAdapter(),
        UnternehmensregisterAdapter(),
        InsolvenzAdapter(),
        OpenCorporatesAdapter(),
        WhoisDenicAdapter(),
        SSLLabsAdapter(),
    ]


def _pre_check_query(company: Company) -> dict:
    # Нормалізуємо вхід: якщо назва порожня або '---', не використовуємо її.
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


def _enrich_company_from_vies(company: Company, vies_data: dict):
    # Не затираємо name, якщо VIES повернув None/'---'.
    v_name = vies_data.get("name")
    v_addr = vies_data.get("address")
    v_country = vies_data.get("country_code")

    changed = False
    if v_country and not (company.country and company.country.strip()):
        company.country = v_country; changed = True
    if v_addr and not (company.address and company.address.strip()):
        company.address = v_addr; changed = True
    if v_name and not (company.name and company.name.strip() and company.name.strip() != "---"):
        company.name = v_name; changed = True

    if changed:
        db.session.add(company)
        db.session.commit()


def _run_checks(company_id: int):
    c = db.session.get(Company, company_id)
    if not c:
        return

    q = _pre_check_query(c)
    results = []
    vies_result = None

    for adapter in _adapters():
        try:
            res = adapter.fetch(q)
        except Exception as e:
            # захист від падіння всього пайплайна
            res = {"status": "unknown", "data": {"error": str(e), "used_query": q}, "source": getattr(adapter, "SOURCE", "unknown")}
        results.append(res)

        # якщо це VIES і є дані — збагачуємо компанію для наступних адаптерів
        if getattr(adapter, "SOURCE", "") == "vies" and isinstance(res.get("data"), dict):
            vies_result = res

    # Після першого кола — за бажанням можемо оновити company і прогнати частину адаптерів ще раз,
    # але для MVP достатньо одноразово:
    if vies_result and isinstance(vies_result.get("data"), dict):
        _enrich_company_from_vies(c, vies_result["data"])

    prev = c.current_status or "unknown"
    apply_results(c, results)
    if prev != c.current_status:
        notify_status_change(c.id, prev, c.current_status)


# Celery інтеграція
def _register_tasks(celery_app):
    @celery_app.task(name="run_full_check_task")
    def run_full_check_task(company_id: int):
        _run_checks(company_id)
        return {"company_id": company_id, "done": True}

    @celery_app.task(name="daily_monitoring_task")
    def daily_monitoring_task():
        subs = MonitoringSubscription.query.filter_by(enabled=True).all()
        for s in subs:
            run_full_check_task.delay(s.company_id)
        return {"scheduled": len(subs)}


# bootstrap
from flask import current_app
try:
    celery = current_app.celery_app  # уже створено у фабриці додатку
    _register_tasks(celery)
except Exception:
    # при імпорті поза контекстом приложення — ок
    pass