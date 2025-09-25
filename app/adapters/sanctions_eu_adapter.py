"""
app/adapters/sanctions_eu_adapter.py
Real EU sanctions adapter: downloads consolidated EU sanctions list (CSV), caches it to app/data/sanctions_eu.csv,
and fuzzy-matches company names / VATs using rapidfuzz. Requires pandas and rapidfuzz.
"""

import os
import os, time
from .base import CheckResult
from flask import current_app
from rapidfuzz import fuzz
from ..utils.http import requests_session_with_retries
from ..utils.logging import get_logger

try:
    import pandas as pd
except Exception:
    pd = None

DATA_DIR = None
CSV_PATH = None

# Декілька запасних URL (можеш налаштувати під себе в .env)
EU_FALLBACK_URLS = [
    "https://www.sanctionsmap.eu/api/v1/sanctions/consolidated/csv",
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw",
]

class EUSanctionsAdapter:
    SOURCE = "sanctions_eu"

    def _ensure_csv(self):
        global CSV_PATH, DATA_DIR
        if not DATA_DIR:
            DATA_DIR = current_app.config.get('CACHE_DIR') or os.path.join(os.path.dirname(__file__), "..", "data")
            CSV_PATH = os.path.join(DATA_DIR, 'sanctions_eu.csv')
        os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

        ttl = int(current_app.config.get('SANCTIONS_EU_CACHE_TTL', 24*3600))
        need = True
        if os.path.exists(CSV_PATH):
            age = time.time() - os.path.getmtime(CSV_PATH)
            if age < ttl and os.path.getsize(CSV_PATH) > 0:
                need = False
        if not need:
            return

        if not pd:
            raise RuntimeError("pandas is required for EU sanctions adapter")

        logger = get_logger()
        logger.info("Downloading EU sanctions CSV to %s", CSV_PATH)
        s = requests_session_with_retries()
        # головний URL з .env, якщо заданий
        primary = current_app.config.get('SANCTIONS_EU_CSV_URL')
        urls = [primary] if primary else []
        urls.extend([u for u in EU_FALLBACK_URLS if u and u not in urls])

        last_error = None
        for url in urls:
            if not url:
                continue
            try:
                r = s.get(url, timeout=getattr(s, "request_timeout", 60), allow_redirects=True)
                r.raise_for_status()
                with open(CSV_PATH, "wb") as f:
                    f.write(r.content)
                return
            except Exception as e:
                last_error = e
                continue

        # Якщо всі джерела впали — не видаляй існуючий кеш, просто залиши як є.
        if not os.path.exists(CSV_PATH):
            raise RuntimeError(f"Failed to download EU sanctions CSV: {last_error}")

    def _load_df(self):
        if not os.path.exists(CSV_PATH) or os.path.getsize(CSV_PATH) == 0:
            return None
        # Спробуємо різні розділювачі
        for sep in (",",";","\t","|"):
            try:
                df = pd.read_csv(CSV_PATH, dtype=str, sep=sep, on_bad_lines="skip").fillna("")
                if df.shape[1] >= 1:
                    return df
            except Exception:
                continue
        return None

    def _name_cols(self, df):
        for c in df.columns:
            cl = c.lower()
            if any(k in cl for k in ("name","entity","subject","designation","target")):
                yield c

    def fetch(self, query: dict) -> CheckResult:
        name = (query.get("name") or "").strip()
        if not name:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "name not provided"}

        self._ensure_csv()
        df = self._load_df()
        if df is None:
            return {"status": "unknown", "data": {}, "source": self.SOURCE, "note": "EU CSV unavailable"}

        name_cols = list(self._name_cols(df)) or [df.columns[0]]

        best_score = 0
        matched = None
        for _, row in df.iterrows():
            for col in name_cols:
                score = fuzz.token_sort_ratio(name.lower(), str(row.get(col, "")).lower())
                if score > best_score:
                    best_score = score
                    matched = str(row.get(col, ""))

        crit = int(current_app.config.get('SANCTIONS_EU_FUZZY_THRESHOLD', 92))
        warn = int(current_app.config.get('SANCTIONS_EU_FUZZY_WARN', 80))
        if best_score >= crit:
            return {"status": "critical", "data": {"match_score": best_score, "matched_name": matched}, "source": self.SOURCE, "note": "EU sanction probable match"}
        elif best_score >= warn:
            return {"status": "warning", "data": {"match_score": best_score, "matched_name": matched}, "source": self.SOURCE, "note": "EU sanction possible match"}
        return {"status": "ok", "data": {"match_score": best_score}, "source": self.SOURCE, "note": "No match in EU sanctions"}