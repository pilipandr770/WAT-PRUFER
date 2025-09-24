from datetime import datetime
from ..extensions import db
from ..models import Company, Check, CheckResult, CheckEvent

SEVERITY_SCORE = {"ok": 0, "warning": 10, "unknown": 5, "critical": 100}


def aggregate_status(results: dict) -> str:
    statuses = [r.get("status", "unknown") for r in results.values()]
    if "critical" in statuses:
        return "critical"
    if "error" in statuses:
        return "error"
    if "ok" in statuses:
        return "ok"
    return "unknown"


def compute_confidence(results: dict) -> int:
    total = 0
    for r in results.values():
        sev = r.get("status", "unknown")
        total += SEVERITY_SCORE.get(sev, 5)
    score = max(0, 100 - min(total, 100))
    return score


def persist_check_results(company_id: int, results: dict) -> Check:
    company = db.session.get(Company, company_id)
    if not company:
        raise ValueError("Company not found")

    status = aggregate_status(results)
    check = Check(company_id=company.id, status=status)
    db.session.add(check)
    db.session.flush()  # ensure check.id

    # create individual adapter results
    for adapter_name, res in results.items():
        # merge data and used_query into details for later inspection
        details = res.get("data", {}) or {}
        used_q = res.get("used_query")
        if used_q:
            details = {**details, "used_query": used_q}
        cr = CheckResult(
            check_id=check.id,
            adapter_name=adapter_name,
            status=res.get("status", "unknown"),
            details=details,
        )
        db.session.add(cr)

    # update company aggregated fields
    previous_status = company.current_status or "unknown"
    company.current_status = status
    company.confidence_score = compute_confidence(results)
    company.last_checked = datetime.utcnow()

    if previous_status != company.current_status:
        ev = CheckEvent(
            company_id=company.id,
            event_type="status_changed",
            payload={"from": previous_status, "to": company.current_status},
        )
        db.session.add(ev)

    db.session.commit()
    return check
