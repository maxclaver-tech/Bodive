from .memory import Refused

# Reserve at least the full documented context for eligible standard Messages models.
INPUT_BILLING_BOUND = 1_000_000
OUTPUT_BILLING_BOUND = 1_600
RATE_FLOORS = {
    "claude-haiku-4-5-20251001": (200, 1000),
    "claude-sonnet-4-6": (600, 3000),
}


def claude_commitment(model, input_cents_per_million, output_cents_per_million):
    floor = RATE_FLOORS.get(model)
    if floor is None:
        raise Refused("Claude model is outside the supported standard Messages models")
    if input_cents_per_million < floor[0] or output_cents_per_million < floor[1]:
        raise Refused(f"Claude rates must be at least {floor[0]}/{floor[1]} EUR cents per million")
    numerator = (INPUT_BILLING_BOUND * input_cents_per_million
                 + OUTPUT_BILLING_BOUND * output_cents_per_million)
    return (numerator + 999_999) // 1_000_000
