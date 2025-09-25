# app/routes/api.py
# REST API для пошуку/перевірок/історії

from flask import Blueprint, request, jsonify, current_app
from ..extensions import db
from ..models import Company, Check, CheckEvent
from ..services.normalizer import normalize_company_query
from ..workers.tasks import _run_checks
from datetime import datetime

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.post("/companies/lookup")
def companies_lookup():
    """
    Приймає будь-які відомі поля (vat_number/name/website/address),
    створює/оновлює компанію і запускає фонову перевірку.
    """
    payload = request.get_json(force=True, silent=True) or {}

    vat = (payload.get("vat_number") or "").strip()
    name = (payload.get("name") or "").strip()
    country = (payload.get("country") or "").strip()
    address = (payload.get("address") or "").strip()
    website = (payload.get("website") or "").strip()

    # requester з тіла або з .env
    requester = payload.get("requester") or {
        "country_code": current_app.config.get("REQUESTER_COUNTRY_CODE", ""),
        "vat_number":  current_app.config.get("REQUESTER_VAT_NUMBER", ""),
    }

    company = Company(vat_number=vat, name=name, country=country, address=address, website=website)
    db.session.add(company); db.session.commit()

    _run_checks(company.id, requester=requester)

    return jsonify({"id": company.id}), 200

    return jsonify({"company_id": company.id, "status": "completed"})

@api_bp.get("/companies")
def companies_list():
    q = request.args.get("q", "")
    query = Company.query
    if q:
        like = f"%{q}%"
        query = query.filter((Company.name.ilike(like)) | (Company.vat_number.ilike(like)))
    items = query.order_by(Company.created_at.desc()).limit(100).all()
    return jsonify([
        {
            "id": c.id,
            "name": c.name,
            "vat_number": c.vat_number,
            "country": c.country,
            "status": c.current_status,
            "confidence_score": c.confidence_score,
            "last_checked": c.last_checked.isoformat() if c.last_checked else None
        } for c in items
    ])

@api_bp.get("/companies/<int:company_id>")
def company_detail(company_id: int):
    c = Company.query.get_or_404(company_id)
    checks = Check.query.filter_by(company_id=company_id).order_by(Check.created_at.desc()).all()
    return jsonify({
        "id": c.id,
        "name": c.name,
        "vat_number": c.vat_number,
        "country": c.country,
        "address": c.address,
        "website": c.website,
        "status": c.current_status,
        "confidence_score": c.confidence_score,
        "last_checked": c.last_checked.isoformat() if c.last_checked else None,
        "checks": [
            {
                "id": chk.id,
                "type": chk.check_type,
                "status": chk.status,
                "created_at": chk.created_at.isoformat(),
                "result": chk.result
            } for chk in checks
        ]
    })

@api_bp.get("/companies/<int:company_id>/history")
def company_history(company_id: int):
    events = CheckEvent.query.filter_by(company_id=company_id).order_by(CheckEvent.created_at.desc()).all()
    return jsonify([
        {
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at.isoformat()
        } for e in events
    ])

@api_bp.post("/companies/<int:company_id>/manual_check")
def manual_check(company_id: int):
    c = Company.query.get_or_404(company_id)
    _run_checks(c.id)
    return jsonify({"company_id": c.id, "status": "queued"})