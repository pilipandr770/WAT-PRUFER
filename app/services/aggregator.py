# app/services/aggregator.py
# Агрегатор: зливає результати адаптерів у Check, оновлює Company.status/score

from datetime import datetime
from ..extensions import db
from ..models import Company, Check, CheckEvent

SEVERITY_SCORE = {"ok": 0, "warning": 10, "unknown": 5, "critical": 100}

def apply_results(company: Company, results: list[dict]) -> None:
    total = 0
    worst = "ok"

    for res in results:
        chk = Check(
            company_id=company.id,
            check_type=res.get("source"),
            result=res.get("data"),
            status=res.get("status", "unknown"),
        )
        db.session.add(chk)

        # Обчислення score
        sev = res.get("status", "unknown")
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
            payload={"from": previous_status, "to": company.current_status}
        )
        db.session.add(ev)

    db.session.commit()