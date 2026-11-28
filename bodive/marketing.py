"""Offline campaign drafts; no sending, scheduling or external calls."""
from datetime import date, timedelta
from .memory import Refused
from .budget_product import TOPIC

def campaign(memory, identifier, language, start):
    memory.check_running()
    if language not in {"es", "en"}:
        raise Refused("Unsupported campaign language")
    try:
        day = date.fromisoformat(start)
        if day.isoformat() != start or day.year > 9998:
            raise ValueError()
    except (TypeError, ValueError):
        raise Refused("Use YYYY-MM-DD")
    dossier = memory.load(identifier)
    if dossier["evidence"]["topic"].strip().casefold() != TOPIC:
        raise Refused("No reviewed campaign template for this topic")
    texts = {
        "es": (
            "¿Sabes cuánto queda después de tus gastos? Compara ingresos y gastos previstos con los reales.",
            "Ejemplo hipotético: 2.000 EUR de ingresos menos 1.500 EUR de gastos dejan 500 EUR de saldo neto.",
            "Una plantilla mensual puede ayudarte a organizar tus cifras. ¿Qué categorías te resultan más útiles?",
        ),
        "en": (
            "How much remains after expenses? Compare planned and actual income and spending.",
            "Hypothetical example: EUR 2,000 income minus EUR 1,500 expenses leaves EUR 500 net cash.",
            "A monthly spreadsheet can help organize your figures. Which categories are most useful to you?",
        ),
    }
    items = [{"date": (day + timedelta(days=offset)).isoformat(),
              "channel": channel, "copy": copy, "status": "private_draft",
              "review_required": True}
             for offset, channel, copy in zip((0, 3, 6), ("social_post", "educational_post", "community_question"), texts[language])]
    memory.check_running()
    return {"dossier_id": identifier, "language": language, "status": "private_draft",
            "published": False, "scheduled": False, "budget_cents": 0,
            "metrics": {"impressions": None, "clicks": None, "sales": None},
            "review": ["Verify product claims", "Check channel rules", "Obtain separate authorization"],
            "items": items}
