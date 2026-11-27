def listing(topic, cents):
    return {
        "platform": "Gumroad",
        "title": f"{topic.title()} Experiment Workbook",
        "description": "Measure a baseline, test one workflow change, and use a decision checklist "
                       "to record what you learned. Includes a reusable trial log in Markdown.",
        "price_cents": cents,
        "currency": "EUR",
        "marketing": "Draft an educational post for an owned or opt-in channel. "
                     "Explain the experiment with a concrete example and link after approval.",
        "status": "draft",
    }
