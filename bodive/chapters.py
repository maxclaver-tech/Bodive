"""Bounded chapter plans and deterministic assembly."""
import json
from .memory import Refused

OUTLINE = (
    "Goals and success criteria",
    "Preparation and baseline",
    "Step-by-step workflow",
    "Worked example",
    "Reusable worksheets and checklists",
    "Evaluation and next steps",
)
LIMIT = 2400

def prompt(topic, number):
    if type(number) is not int or not 1 <= number <= len(OUTLINE):
        raise Refused("Invalid chapter number")
    index = "; ".join(f"{i}: {title}" for i, title in enumerate(OUTLINE, 1))
    return (f"Write ONLY chapter {number} ({OUTLINE[number-1]}) of an original English "
            f"practical workbook about {topic}. Outline: {index}. "
            "Aim for 500-750 words, finish well before the output limit. "
            "Use concise Markdown, practical exercises and topic-specific examples; "
            "do not duplicate other chapters, invent statistics, copy third-party content, "
            "insert links or request external actions. End with a complete sentence.")

def assemble(memory, dossier_id, identifiers):
    if len(identifiers) != len(OUTLINE) or len(set(identifiers)) != len(OUTLINE):
        raise Refused("Exactly six distinct chapter approvals are required")
    parts = {}
    seen = set()
    for identifier in identifiers:
        row = memory.get(identifier)
        payload = json.loads(row["payload"])
        result = json.loads(row["result"] or "{}")
        number = payload.get("chapter")
        draft = result.get("draft")
        if (row["kind"] != "claude" or row["status"] != "done" or row["blocked"]
                or payload.get("dossier_id") != dossier_id or type(number) is not int
                or not 1 <= number <= len(OUTLINE) or number in parts
                or result.get("stop_reason") != "end_turn"
                or not isinstance(draft, str) or not draft.strip()):
            raise Refused("Each chapter must be complete, reconciled and from this dossier")
        normalized = " ".join(draft.casefold().split())
        if normalized in seen:
            raise Refused("Duplicate chapter text")
        seen.add(normalized)
        parts[number] = draft.strip()
    topic = memory.load(dossier_id)["evidence"]["topic"]
    index = "\n".join(f"{i}. {title}" for i, title in enumerate(OUTLINE, 1))
    return f"# {topic.title()} Workbook\n\n## Contents\n\n{index}\n\n" + "\n\n".join(
        f"## Chapter {i}: {title}\n\n{parts[i]}" for i, title in enumerate(OUTLINE, 1))
