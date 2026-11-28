"""Hypothetical pricing scenarios, never actual sales or price changes."""
from .memory import Refused

def scenarios(prices, units, fee_bps, fixed_cents, unit_cost_cents):
    if not isinstance(prices, list) or not 1 <= len(prices) <= 20:
        raise Refused("Expected 1–20 prices")
    values = prices + [units, fee_bps, fixed_cents, unit_cost_cents]
    if any(type(v) is not int or not 0 <= v <= 1000000 for v in values) or fee_bps > 10000:
        raise Refused("Invalid scenario inputs")
    rows = []
    for price in sorted(set(prices)):
        fee = (price * fee_bps + 9999) // 10000
        margin = price - fee - unit_cost_cents
        rows.append({"price_cents": price, "unit_margin_cents": margin,
                     "hypothetical_profit_cents": margin * units - fixed_cents,
                     "break_even_units": (fixed_cents + margin - 1)//margin if margin > 0 else None})
    return {"status": "hypothetical", "currency": "EUR", "rows": rows,
            "experiment": "Review evidence and approve a separate pricing experiment",
            "external_changes": False}
