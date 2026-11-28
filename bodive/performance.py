"""Read-only ledger report; no inferred sales."""
def report(memory):
    data = memory.report()
    available = data["available_cents"]
    return {"ledger": data, "source": "internal ledger, not independent provider verification",
            "verified_sales": None, "conversion_rate": None,
            "recommendations": ["Freeze new commitments" if available <= 0 else "Review evidence before any new commitment",
                                "Reconcile provider receipts before interpreting profit"],
            "budget_exhausted": available <= 0}
