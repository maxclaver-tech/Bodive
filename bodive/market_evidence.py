"""Offline review of manually collected public evidence; no scraping."""
from datetime import date
from urllib.parse import urlsplit
from .memory import Refused

def review(records, today):
    if not isinstance(records, list) or len(records) > 100:
        raise Refused("Expected at most 100 evidence records")
    result = []
    seen = set()
    for row in records:
        if not isinstance(row, dict) or set(row) != {"url", "observed", "kind", "note"}:
            raise Refused("Invalid evidence fields")
        if any(not isinstance(v, str) or not v.strip() or len(v)>1000 for v in row.values()):
            raise Refused("Invalid evidence value")
        url = urlsplit(row["url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise Refused("Use a public HTTPS source without credentials or tracking")
        try:
            age = (today - date.fromisoformat(row["observed"])).days
        except ValueError:
            raise Refused("Invalid observation date")
        if age < 0 or row["kind"] not in {"competitor", "interest", "price"}:
            raise Refused("Invalid evidence category or date")
        key = (row["url"], row["kind"])
        if key in seen:
            raise Refused("Duplicate evidence")
        seen.add(key)
        result.append({**row, "expired": age > 30, "independently_verified": False})
    return {"records": result, "demand_validated": False, "status": "manual_review_required"}
