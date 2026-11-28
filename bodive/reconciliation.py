"""Offline reconciliation preview; never books revenue or mutates providers."""
import re
from collections import defaultdict
from hashlib import sha256
import json

def preview(events):
    """Normalized evidence rows, integer minor units, no currency conversion."""
    seen = {}
    conflicts = set()
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid event")
        required = {"id", "sale_id", "currency", "kind", "amount_minor", "evidence"}
        if set(event) != required:
            raise ValueError("Invalid event fields")
        for key in ("id", "sale_id", "evidence"):
            if not isinstance(event[key], str) or not event[key].strip():
                raise ValueError("Missing identity or evidence")
        if not isinstance(event["currency"], str) or not re.fullmatch("[A-Z]{3}", event["currency"]):
            raise ValueError("Invalid currency")
        if event["kind"] not in ("sale", "fee", "refund"):
            raise ValueError("Invalid event kind")
        if type(event["amount_minor"]) is not int or event["amount_minor"] < 0:
            raise ValueError("Invalid amount")
        identity = event["id"]
        if identity in seen and seen[identity] != event:
            conflicts.add(identity)
        else:
            seen[identity] = dict(event)
    totals = defaultdict(lambda: {"sale": 0, "fee": 0, "refund": 0})
    accepted = []
    for identity, event in sorted(seen.items()):
        if identity in conflicts:
            continue
        totals[event["currency"]][event["kind"]] += event["amount_minor"]
        accepted.append(sha256(json.dumps(event, sort_keys=True).encode()).hexdigest())
    return {"status": "unverified_preview", "booked": False,
            "conflicting_ids": sorted(conflicts), "evidence_hashes": accepted,
            "currencies": {currency: dict(values, net=values["sale"]-values["fee"]-values["refund"])
                           for currency, values in sorted(totals.items())}}
