"""Telegram decisions use a dedicated bot and one allowlisted private account."""

import json
import re

from .memory import MANUAL_KINDS, Refused, canonical

ID = r"[0-9a-f]{32}"
DIGEST = r"[0-9a-f]{64}"


def notify(memory, telegram, identifier):
    row = memory.get(identifier)
    telegram.send(
        f"BODIVE {row['kind']} · cap EUR {row['max_cents'] / 100:.2f}\n"
        f"Status: {row['status']} · expires {row['expires_at']}\n"
        f"Review: /review {identifier}\n"
        f"Approve: /approve {identifier} {row['digest']}\n"
        f"Reject: /reject {identifier} {row['digest']}"
    )


def on_message(memory, telegram, message):
    chat = message.get("chat", {})
    sender = message.get("from", {})
    if (chat.get("type") != "private" or chat.get("id") != telegram.operator
            or sender.get("id") != telegram.operator or sender.get("is_bot") is not False
            or "forward_origin" in message or "via_bot" in message):
        return
    text = message.get("text", "").strip()
    actor = f"telegram:{telegram.operator}"
    if text == "/stop":
        memory.stop(actor)
        telegram.send("BODIVE stopped. Pending and approved operations were cancelled.")
        return
    if text == "/budget":
        report = memory.report()
        labels = (("Presupuesto inicial", "budget_cents"), ("Ingresos", "income_cents"),
                  ("Gastos", "expenses_cents"), ("Beneficio", "profit_cents"),
                  ("Comprometido", "committed_cents"), ("Disponible", "available_cents"))
        telegram.send("BODIVE · Presupuesto\n" + "\n".join(
            f"{label}: {report[key] / 100:.2f} EUR" for label, key in labels))
        return
    if match := re.fullmatch(rf"/chapter ({ID}) ([1-6])", text):
        from . import cli
        args = cli.parser().parse_args(["propose-chapter", match[1], match[2]])
        row = cli.proposal(args, memory)
        notify(memory, telegram, row["id"])
        return
    if match := re.fullmatch(rf"/assemble ({ID}) ((?:{ID} ){5}{ID})", text):
        from . import cli
        args = cli.parser().parse_args(["propose-publish", match[1], "--chapter-ids", *match[2].split()])
        row = cli.proposal(args, memory)
        notify(memory, telegram, row["id"])
        return
    if match := re.fullmatch(rf"/dossier ({ID})", text):
        telegram.send(json.dumps(memory.load(match[1]), ensure_ascii=False, indent=2))
        return
    if match := re.fullmatch(rf"/(approve|reject) ({ID}) ({DIGEST})", text):
        verb, identifier, digest = match.groups()
        memory.decide(identifier, digest, verb == "approve", actor)
        telegram.send(f"Recorded: {verb} {identifier}")
        return
    if match := re.fullmatch(rf"/(review|claim|ready|result) ({ID})", text):
        action, identifier = match.groups()
        if action == "claim":
            payload = memory.claim(identifier, MANUAL_KINDS)
            telegram.send("Manual operation claimed. If delivery fails, review its record before acting.\n"
                          + json.dumps(payload, ensure_ascii=False, indent=2))
        elif action == "ready":
            memory.check_claim(identifier, MANUAL_KINDS)
            telegram.send(f"Active manual claim: {identifier}. Verify immediately before acting.")
        else:
            row = memory.get(identifier)
            value = row["payload" if action == "review" else "result"]
            if value is None:
                raise Refused("No result has been recorded")
            data = json.loads(value)
            if action == "result" and row["kind"] == "claude" and "draft" in data:
                status = "Completo" if data.get("stop_reason") == "end_turn" else "INCOMPLETO: no publicar"
                telegram.send(f"BODIVE · Borrador {identifier}\n{status}\n"
                              + data["draft"])
                telegram.send("Datos de generación\n" + json.dumps(
                    {key: val for key, val in data.items() if key != "draft"},
                    ensure_ascii=False, indent=2))
            else:
                telegram.send(f"{identifier} · {row['kind']} · {row['status']}\n"
                              + json.dumps(data, ensure_ascii=False, indent=2))
        return
    telegram.send("Comandos: /chapter DOSIER 1-6, /assemble DOSIER ID1 ID2 ID3 ID4 ID5 ID6, "
                  "/dossier ID, /review ID, /approve ID DIGEST, /reject ID DIGEST, "
                  "/claim ID, /ready ID, /result ID, /budget, /stop")


def poll(memory, telegram):
    for update in telegram.updates(memory.offset()):
        try:
            on_message(memory, telegram, update.get("message", {}))
        except Refused as exc:
            # Decisions and claims already committed remain effective if the reply was lost.
            telegram.send(str(exc))
        memory.offset(update["update_id"] + 1)
