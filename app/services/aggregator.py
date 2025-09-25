# app/services/aggregator.py
# Агрегатор: зливає результати адаптерів у Check, оновлює Company.status/score

from datetime import datetime
from ..extensions import db
from ..models import Company, Check, CheckResult, CheckEvent

SEVERITY_SCORE = {"ok": 0, "warning": 10, "unknown": 5, "critical": 100}


def apply_results(company: Company, results: list[dict]) -> None:
    """Create a single Check row and attach per-adapter CheckResult rows.

    The project's models store a Check (summary) and multiple CheckResult entries
    with adapter-level details. Older code attempted to set fields that don't
    exist on Check; this implementation matches the current models.
    """
    total = 0
    worst = "ok"

    # Summary Check for this run
    chk = Check(company_id=company.id, status="unknown")
    db.session.add(chk)

    for res in results:
        adapter_name = res.get("source") or res.get("adapter") or "unknown"
        status = res.get("status", "unknown")
        details = res.get("data")

        cr = CheckResult(check=chk, adapter_name=adapter_name, status=status, details=details)
        db.session.add(cr)

        # Compute aggregate severity
        sev = status
        total += SEVERITY_SCORE.get(sev, 5)
        if sev == "critical":
            worst = "critical"
        elif sev == "warning" and worst != "critical":
            worst = "warning"
        elif sev == "unknown" and worst == "ok":
            worst = "unknown"

    previous_status = company.current_status or "unknown"
    company.confidence_score = max(0, 100 - min(total, 100))
    company.current_status = worst
    company.last_checked = datetime.utcnow()

    if previous_status != company.current_status:
        ev = CheckEvent(
            company_id=company.id,
            event_type="status_changed",
            payload={"from": previous_status, "to": company.current_status},
        )
        db.session.add(ev)

    db.session.commit()