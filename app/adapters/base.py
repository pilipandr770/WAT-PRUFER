# app/adapters/base.py
# Базовий клас адаптера: уніфікований інтерфейс fetch()

from typing import Protocol, TypedDict, Optional, Any

class CheckResult(TypedDict, total=False):
    status: str       # ok/warning/critical/unknown
    data: dict
    source: str
    note: str

class Adapter(Protocol):
    def fetch(self, query: dict) -> CheckResult: ...