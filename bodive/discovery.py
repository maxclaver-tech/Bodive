"""Explore a small fixed candidate pool; evidence ranks investigation, not profit."""
from . import community
from .memory import Refused, now

CANDIDATES = (
    ("Freelancer client onboarding", "Client onboarding toolkit"),
    ("Project management templates", "Project planning workbook"),
    ("Personal budgeting", "Personal budget spreadsheet"),
    ("Job interview preparation", "Interview preparation workbook"),
)


def discover(memory, http, category="market"):
    rows = []
    # Reserve the complete batch atomically; avoid half-finished searches at quota limit.
    memory.research_slot(category, len(CANDIDATES))
    for topic, product in CANDIDATES:
        memory.check_running()
        try:
            snapshot = community.search(http, topic)
        except Refused:
            rows.append({"topic":topic,"product":product,"status":"unavailable","signals":[]})
            continue
        hits = snapshot["observations"]
        rows.append({"topic":topic,"product":product,"status":"sampled","signals":hits,
                     "discussion_count":len(hits),
                     "comment_count":sum(h["comments"] for h in hits)})
    # Incomplete and empty results are distinct. Neither implies no market.
    rows.sort(key=lambda r:(r["status"]=="sampled",r.get("discussion_count",0),
                           r.get("comment_count",0)),reverse=True)
    return {"collected_at":now().isoformat(),"source":"Hacker News / Algolia",
            "candidates":rows,"interpretation":"Prioridad de revisión por señales de conversación, no demanda ni rentabilidad verificadas."}


def candidate(snapshot, number):
    if not snapshot or type(number) is not int or not 1<=number<=len(snapshot["candidates"]):
        raise Refused("Selecciona un candidato de una búsqueda guardada")
    row = snapshot["candidates"][number-1]
    if row["status"]!="sampled":
        raise Refused("La búsqueda de este candidato no está disponible")
    return row
