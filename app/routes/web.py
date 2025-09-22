# app/routes/web.py
# Простий UI на Jinja2: форма пошуку, список, деталі

from flask import Blueprint, render_template, request, redirect, url_for, current_app
from ..models import Company, Check
from ..extensions import db
from ..services.normalizer import normalize_company_query
from ..workers.tasks import _run_checks

web_bp = Blueprint("web", __name__)

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
            current_status="unknown",
            confidence_score=0,
            raw_source={},
        )
        db.session.add(company)
        db.session.commit()

    _run_checks(company.id)
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
    checks = Check.query.filter_by(company_id=company_id).order_by(Check.created_at.desc()).all()
    return render_template("company_detail.html", company=c, checks=checks)