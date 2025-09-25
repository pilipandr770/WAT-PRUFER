# app/routes/web.py
# Простий UI на Jinja2: форма пошуку, список, деталі

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from ..models import Company, Check, CheckResult
from ..extensions import db
from ..services.normalizer import normalize_company_query
from ..workers.tasks import _run_checks, run_full_check_task

web_bp = Blueprint("web", __name__)

def aggregate_results(results):
    statuses = [result['status'] for result in results.values()]
    if 'critical' in statuses:
        return 'critical'
    elif 'error' in statuses:
        return 'error'
    elif 'ok' in statuses:
        return 'ok'
    else:
        return 'unknown'

@web_bp.get("/")
def index():
    return render_template("index.html")

@web_bp.post("/lookup")
def web_lookup():
    q = normalize_company_query(request.form.to_dict())
    company = Company.query.filter(
        (Company.vat_number == q.get("vat_number")) | (Company.name == q.get("name"))
    ).first()
    if not company:
        company = Company(
            vat_number=q.get("vat_number"),
            name=q.get("name"),
            country=q.get("country"),
            address=q.get("address"),
            website=q.get("website"),
            requester_name=q.get("requester_name"),
            requester_email=q.get("requester_email"),
            requester_org=q.get("requester_org"),
            requester_vat_number=q.get("requester_vat_number"),
            requester_country_code=q.get("requester_country_code"),
            current_status="unknown",
            confidence_score=0,
            raw_source={},
        )
        db.session.add(company)
        db.session.commit()
    else:
        # update requester info if provided
        changed = False
        if q.get("requester_name") and not company.requester_name:
            company.requester_name = q.get("requester_name")
            changed = True
        if q.get("requester_email") and not company.requester_email:
            company.requester_email = q.get("requester_email")
            changed = True
        if q.get("requester_org") and not company.requester_org:
            company.requester_org = q.get("requester_org")
            changed = True
        if q.get("requester_vat_number") and not company.requester_vat_number:
            company.requester_vat_number = q.get("requester_vat_number")
            changed = True
        if q.get("requester_country_code") and not company.requester_country_code:
            company.requester_country_code = q.get("requester_country_code")
            changed = True
        if changed:
            db.session.add(company)
            db.session.commit()

    # enqueue full check task to run in background (or run synchronously if Celery
    # wrapper isn't registered yet, e.g. during tests)
    task_caller = getattr(run_full_check_task, 'delay', run_full_check_task)
    task_caller(company.id, q.get("requester"))
    return redirect(url_for("web.company_detail", company_id=company.id))

@web_bp.get("/companies")
def companies_page():
    q = request.args.get("q", "")
    query = Company.query
    if q:
        like = f"%{q}%"
        query = query.filter((Company.name.ilike(like)) | (Company.vat_number.ilike(like)))
    items = query.order_by(Company.created_at.desc()).limit(100).all()
    return render_template("companies.html", companies=items, q=q)

@web_bp.get("/companies/<int:company_id>")
def company_detail(company_id: int):
    c = Company.query.get_or_404(company_id)
    check = Check.query.filter_by(company_id=company_id).order_by(Check.created_at.desc()).first()
    return render_template("company_detail.html", company=c, check=check)