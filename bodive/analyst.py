from .memory import Refused

GUMROAD_PRICING = "https://gumroad.com/pricing"


def analyze(evidence, price_cents, unit_cost_cents, fixed_cost_cents):
    if not 1 <= price_cents <= 1_000_000:
        raise Refused("Price must be 1–1000000 EUR cents")
    if not 0 <= unit_cost_cents <= 1_000_000 or not 0 <= fixed_cost_cents <= 10_000:
        raise Refused("Invalid estimated commercial costs")
    margin = price_cents - unit_cost_cents
    break_even = (fixed_cost_cents + margin - 1) // margin if margin > 0 else None
    return {
        "currency": "EUR", "demand": "Unverified; repository activity measures developer interest only.",
        "competition": {
            "potential_free_alternatives": [row["url"] for row in evidence["observations"]],
            "paid_competition": "Unverified; review actual competitor listings before launch.",
        },
        "risks": ["No validated willingness to pay", "Free substitutes",
                  "Fee, refund, tax and FX variations", "Review draft for originality and rights"],
        "assumptions": {"price_cents": price_cents, "estimated_total_unit_cost_cents": unit_cost_cents,
                        "estimated_fixed_cost_cents": fixed_cost_cents,
                        "clarification": "Operator scenario. Include fees, FX and refunds in unit costs.",
                        "fee_reference": GUMROAD_PRICING},
        "profit_scenarios_cents": {str(n): n * margin - fixed_cost_cents for n in (0, 10, 25)},
        "break_even_units": break_even,
    }
