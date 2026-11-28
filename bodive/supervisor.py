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
    if row["status"] == "pending":
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
    if match := re.fullmatch(rf"/evidence ({ID}) (competitor|interest|purchase) (\S{{1,350}}) (.{1,300})", text):
        memory.market_observation(*match.groups(), actor)
        telegram.send("Observación aportada por operador guardada. No equivale a verificación independiente.")
        return
    if text in {"/discover", "/opportunities"}:
        from . import discovery
        if text == "/discover":
            if memory.mode != "live":
                raise Refused("La búsqueda externa requiere modo live")
            telegram.send("Investigando cuatro categorías. No se realizará ninguna inversión.")
            snapshot = discovery.discover(memory, telegram.http)
            identifier = memory.record_discovery(snapshot)
        else:
            detail = memory.get_discovery()
            if detail is None:
                telegram.send("Sin oportunidades guardadas. Usa /discover.")
                return
            identifier, snapshot = detail["discovery_id"],detail["snapshot"]
        telegram.send(f"BODIVE · Candidatos comerciales\n{snapshot['collected_at']}\n"
                      f"{snapshot['interpretation']}\nFuente: {snapshot['source']}")
        for n,row in enumerate(snapshot["candidates"],1):
            if row["status"]!="sampled":
                telegram.send(f"{n}. {row['product']} · fuente no disponible")
                continue
            links = "\n".join(f"{h['title']}\n{h['url']}" for h in row["signals"][:2])
            telegram.send(f"{n}. {row['product']}\n"
                          f"Publicaciones de muestra: {row['discussion_count']} · comentarios: {row['comment_count']}\n"
                          f"{links}\n/shortlist {identifier} {n}")
        return
    if match := re.fullmatch(rf"/shortlist ({ID}) ([1-4])", text):
        from . import discovery, director
        detail = memory.get_discovery(match[1])
        row = discovery.candidate(detail["snapshot"] if detail else None, int(match[2]))
        # Creates a local research dossier only. No extra network requests or spending.
        identifier = director.plan(memory, row["product"], 1200, 400, 0, None)
        memory.record_community(identifier, {"source":detail["snapshot"]["source"],
            "query":row["topic"],"collected_at":detail["snapshot"]["collected_at"],
            "observations":row["signals"],"interpretation":detail["snapshot"]["interpretation"]})
        telegram.send(f"Dosier de revisión: {identifier}\n/market {identifier}\n/signals {identifier}\n"
                      "Precio y costes iniciales hipotéticos; demanda no validada.")
        return
    if match := re.fullmatch(rf"/(scan|signals) ({ID})", text):
        from .community import search
        action, identifier = match.groups()
        dossier = memory.load(identifier)
        if action == "scan":
            if memory.mode != "live":
                raise Refused("La búsqueda externa requiere modo live")
            memory.research_slot()
            snapshot = search(telegram.http, dossier["evidence"]["topic"])
            memory.record_community(identifier, snapshot)
        else:
            snapshot = memory.latest_community(identifier)
        if snapshot is None:
            telegram.send("Sin búsqueda guardada. Usa /scan DOSIER.")
            return
        telegram.send(f"BODIVE · {snapshot['source']}\nTema: {snapshot['query']}\n"
                      f"Fecha UTC: {snapshot['collected_at']}\n"
                      f"Resultados de muestra: {len(snapshot['observations'])}\n"
                      f"{snapshot['interpretation']}\nNo encontrar resultados no demuestra ausencia de demanda.")
        for item in snapshot["observations"]:
            telegram.send(f"{item['title']}\n{item['url']}\n"
                          f"Puntos: {item['points']} · Comentarios: {item['comments']}\n{item['published_at']}")
        return
    if match := re.fullmatch(rf"/market ({ID})", text):
        from .market import assessment
        identifier = match[1]
        data = assessment(memory.load(identifier), memory.market_observations(identifier),
                          memory.product_report(identifier)["cost_cents"])
        be = str(data["break_even"]) if data["break_even"] is not None else "no alcanzable"
        telegram.send(f"BODIVE · Viabilidad comercial\n{data['topic']}\n"
                      f"{data['verdict']}\n"
                      f"Precio supuesto: {data['price']/100:.2f} EUR\n"
                      f"Coste unitario supuesto: {data['unit_cost']/100:.2f} EUR\n"
                      f"Margen supuesto: {data['margin']/100:.2f} EUR\n"
                      f"Coste fijo mínimo estimado: {data['fixed_floor']/100:.2f} EUR\n"
                      f"Punto de equilibrio mínimo: {be} ventas\n"
                      "Escenarios (no previsiones): "+", ".join(f"{n} ventas: {v/100:.2f} EUR" for n,v in data["scenarios"].items())+
                      f"\nSeñales GitHub: {data['repository_signals']} (no prueban demanda)\n"
                      f"URLs aportadas últimos 30 días: {data['counts']}\n"
                      "Faltan verificar demanda, precios, comisiones y costes comunes.")
        for item in data["observations"]:
            telegram.send(f"{item['kind']} · {item['url']}\n{item['note']}\nNo verificado")
        return
    if text == "/pending":
        rows = memory.pending_costs()
        if not rows:
            telegram.send("No hay operaciones pendientes de conciliación.")
        for row in rows:
            result = json.loads(row["result"] or "{}")
            usage = result.get("usage", {})
            telegram.send(f"{row['id']} | {row['kind']} | reserva {row['max_cents']/100:.2f} EUR\n"
                          f"UTC: {row['claimed_at']}\nResultado: {result.get('stop_reason', 'sin resultado')}\n"
                          f"Uso: {json.dumps(usage, ensure_ascii=False)}\n"
                          "Verifica la factura del proveedor antes de conciliar.")
        return
    if match := re.fullmatch(rf"/reconcile ({ID}) ([0-9]{{1,5}}) ([A-Za-z0-9._-]{{1,100}}) CONFIRMO", text):
        identifier, cents, reference = match.groups()
        memory.finish(identifier, int(cents), reference, actor=actor)
        telegram.send(f"Coste verificado registrado: {int(cents)/100:.2f} EUR. Reserva conciliada.\n/budget")
        return
    if match := re.fullmatch(r"/hosting ([0-9]{1,5}) ([A-Za-z0-9._-]{1,100}) CONFIRMO", text):
        cents, reference = match.groups()
        memory.hosting_cost(int(cents), reference, actor)
        telegram.send(f"Factura de alojamiento registrada: {int(cents)/100:.2f} EUR.\n/budget")
        return
    if match := re.fullmatch(rf"/product ({ID})", text):
        report = memory.product_report(match[1])
        telegram.send(f"BODIVE · {report['topic']}\n"
                      f"Capítulos completos: {report['completed_chapters']}\n"
                      f"Costes directos registrados: {report['cost_cents']/100:.2f} EUR\n"
                      f"Reservas pendientes: {report['reserved_cents']/100:.2f} EUR\n"
                      "Ingresos por producto y reparto de costes comunes todavía no disponibles.")
        return
    if match := re.fullmatch(rf"/pdf ({ID})", text):
        from .pdf_export import from_approval
        document = from_approval(memory, match[1])
        telegram.document(document, "bodive-review.pdf")
        telegram.send("PDF para revisión. No implica autorización ni publicación.")
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
    telegram.send("Comandos: /discover, /opportunities, /shortlist BUSQUEDA N, /scan DOSIER, /signals DOSIER, /market DOSIER, /evidence DOSIER competitor|interest|purchase URL NOTA, /pending, /reconcile ID CENTIMOS RECIBO CONFIRMO, /hosting CENTIMOS RECIBO CONFIRMO, /product DOSIER, /pdf ID, /plan TEMA, /run ID, /notify ID, /chapter DOSIER 1-6, /assemble DOSIER ID1 ID2 ID3 ID4 ID5 ID6, "
                  "/dossier ID, /review ID, /approve ID DIGEST, /reject ID DIGEST, "
                  "/claim ID, /ready ID, /result ID, /budget, /stop")


def poll(memory, telegram):
    with memory.poll_lock() as acquired:
        if not acquired:
            return False
        _poll_locked(memory, telegram)
        return True


def _poll_locked(memory, telegram):
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
