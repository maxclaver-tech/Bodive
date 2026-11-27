"""Telegram decisions use a dedicated bot and one allowlisted private account."""

import json
import re

from .memory import MANUAL_KINDS, Refused, canonical

ID = r"[0-9a-f]{32}"
DIGEST = r"[0-9a-f]{64}"


def button(label, action, row):
    # 2 + 32 + 1 + 24 = 59 ASCII bytes, within Telegram's 64-byte limit.
    return {"text": label, "callback_data": f"{action}:{row['id']}:{row['digest'][:24]}"}


def notify(memory, telegram, identifier):
    row = memory.get(identifier)
    payload = json.loads(row["payload"])
    scope = payload.get("prompt") if row["kind"] == "claude" else None
    summary = (f"BODIVE · {row['kind']} · máximo {row['max_cents'] / 100:.2f} EUR\n"
               f"Estado: {row['status']} · vence {row['expires_at']}\n"
               f"ID: {identifier}")
    if scope and len(scope) <= 2000:
        summary += f"\nModelo: {payload['model']} · tokens: {payload.get('max_tokens', 1600)}\n{scope}"
    rows = [[button("Revisar contenido", "v", row)]]
    if row["status"] == "pending":
        # Review is always available, and non-Claude proposals may contain long scopes.
        rows.append([button("Aprobar", "a", row), button("Rechazar", "r", row)])
    if row["kind"] == "claude" and row["status"] == "approved":
        rows.append([button("Generar ahora", "g", row)])
    telegram.buttons(summary, rows)
    # Keep full hash commands available for older clients and audits.
    telegram.send(f"/approve {identifier} {row['digest']}\n/reject {identifier} {row['digest']}")


def on_callback(memory, telegram, callback):
    message = callback.get("message", {})
    chat = message.get("chat", {})
    sender = callback.get("from", {})
    if (chat.get("type") != "private" or chat.get("id") != telegram.operator
            or sender.get("id") != telegram.operator or sender.get("is_bot") is not False):
        return None
    match = re.fullmatch(rf"([avrg]):({ID}):([0-9a-f]{{24}})", callback.get("data", ""))
    if not match:
        return None
    action, identifier, prefix = match.groups()
    row = memory.get(identifier)
    if row["digest"][:24] != prefix:
        raise Refused("La solicitud no coincide con la versión del botón")
    actor = f"telegram:{telegram.operator}"
    if action in ("a", "r"):
        memory.decide(identifier, row["digest"], action == "a", actor)
        telegram.answer(callback["id"], "Aprobado" if action == "a" else "Rechazado")
        notify(memory, telegram, identifier)
    elif action == "v":
        telegram.answer(callback["id"], "Revisión")
        telegram.send(json.dumps(json.loads(row["payload"]), ensure_ascii=False, indent=2))
    elif action == "g":
        if row["kind"] != "claude" or row["status"] != "approved":
            raise Refused("Se requiere una autorización de Claude vigente")
        telegram.answer(callback["id"], "Solicitud recibida")
        return identifier
    return None


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
    if match := re.fullmatch(rf"/run ({ID})", text):
        return match[1]
    if match := re.fullmatch(rf"/notify ({ID})", text):
        notify(memory, telegram, match[1])
        return
    if match := re.fullmatch(r"/plan (.{1,120})", text):
        from . import cli
        args = cli.parser().parse_args(["plan", "--", match[1]])
        result = cli.execute(args, memory, telegram.http)
        telegram.send(f"Dosier creado: {result['id']}\n/dossier {result['id']}")
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
        notify(memory, telegram, identifier)
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
    telegram.send("Comandos: /plan TEMA, /run ID, /notify ID, /chapter DOSIER 1-6, /assemble DOSIER ID1 ID2 ID3 ID4 ID5 ID6, "
                  "/dossier ID, /review ID, /approve ID DIGEST, /reject ID DIGEST, "
                  "/claim ID, /ready ID, /result ID, /budget, /stop")


def poll(memory, telegram):
    # Process decisions and stop commands before starting any paid operation.
    # Run at most one explicitly requested generation per poll; never auto-retry.
    requested = []
    for update in telegram.updates(memory.offset()):
        try:
            if "callback_query" in update:
                identifier = on_callback(memory, telegram, update["callback_query"])
            else:
                identifier = on_message(memory, telegram, update.get("message", {}))
            if identifier and identifier not in requested:
                requested.append(identifier)
        except Refused as exc:
            telegram.send(str(exc))
        memory.offset(update["update_id"] + 1)
    if requested:
        from . import cli
        identifier = requested[0]
        if len(requested) > 1:
            telegram.send("Solo una generación por sondeo. Solicita las demás de nuevo explícitamente.")
        try:
            args = cli.parser().parse_args(["run-claude", identifier])
            result = cli.execute(args, memory, telegram.http)
            status = "Completo" if result["complete_draft"] else "INCOMPLETO: no publicar"
            telegram.send(f"Generación guardada: {status}\n/result {identifier}\n"
                          "Conciliación del coste pendiente.")
        except Refused as exc:
            telegram.send(f"No se completó la generación: {exc}. Revisa el estado antes de repetir.")
        except Exception:
            telegram.send("Error de generación. Revisa la solicitud y el coste antes de repetir.")
