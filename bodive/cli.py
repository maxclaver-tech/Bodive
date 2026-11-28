import argparse
import json
import os
import re
import sys

from . import chapters, creator, director, finance, gumroad, supervisor
from .connectors import Claude, GitHubResearch, Http, Telegram
from .memory import MANUAL_KINDS, Memory, Refused


def required(name, pattern=None):
    value = os.environ.get(name, "")
    if not value or (pattern and not re.fullmatch(pattern, value)):
        raise Refused(f"Missing or invalid setting: {name}")
    return value


def telegram(http):
    return Telegram(http, required("TELEGRAM_BOT_TOKEN", r"[0-9]+:[A-Za-z0-9_-]+"),
                    int(required("TELEGRAM_OPERATOR_ID", r"[1-9][0-9]{0,15}")))


def parser():
    root = argparse.ArgumentParser(prog="bodive")
    commands = root.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("topic")
    plan.add_argument("--price", type=int, default=1200)
    plan.add_argument("--unit-cost", type=int, default=400)
    plan.add_argument("--fixed-cost", type=int, default=0)
    for name in ("show", "approval", "notify", "claim", "run-claude", "propose-claude"):
        commands.add_parser(name).add_argument("id")
    publication = commands.add_parser("propose-publish")
    publication.add_argument("id")
    publication.add_argument("--draft-id")
    publication.add_argument("--chapter-ids", nargs=6)
    for name in ("artifact-review", "artifact-handoff"):
        artifact = commands.add_parser(name)
        artifact.add_argument("dossier")
        artifact.add_argument("file")
        if name == "artifact-handoff":
            artifact.add_argument("approval")
    chapter = commands.add_parser("propose-chapter")
    chapter.add_argument("id")
    chapter.add_argument("chapter", type=int)
    manual = commands.add_parser("propose-manual")
    manual.add_argument("kind", choices=("advertise", "expense"))
    manual.add_argument("cents", type=int)
    manual.add_argument("description")
    decide = commands.add_parser("simulate-decision")
    decide.add_argument("id")
    decide.add_argument("verdict", choices=("approve", "reject"))
    for name in ("complete", "income"):
        entry = commands.add_parser(name)
        if name == "complete":
            entry.add_argument("id")
        entry.add_argument("cents", type=int)
        entry.add_argument("reference")
    for name in ("poll", "serve", "stop", "resume", "report", "events"):
        commands.add_parser(name)
    return root


def proposal(args, memory):
    if args.command == "propose-manual":
        if not 1 <= len(args.description.strip()) <= 1800:
            raise Refused("Describe exact scope, vendor or channel, and approved copy if advertising")
        return memory.propose(args.kind, {"instructions": args.description}, args.cents)
    dossier = memory.load(args.id)
    if args.command == "propose-publish":
        if args.chapter_ids:
            if args.draft_id:
                raise Refused("Choose either a draft or six chapters")
            dossier["product_markdown"] = chapters.assemble(memory, args.id, args.chapter_ids)
        if args.draft_id:
            draft = memory.get(args.draft_id)
            if (draft["kind"] != "claude" or draft["status"] != "done" or draft["blocked"]
                    or json.loads(draft["payload"])["dossier_id"] != args.id
                    or "chapter" in json.loads(draft["payload"])
                    or not draft["result"]
                    or not json.loads(draft["result"]).get("draft")
                    or json.loads(draft["result"]).get("stop_reason") != "end_turn"):
                raise Refused("Use a reconciled and valid Claude draft from this dossier")
            dossier["product_markdown"] = json.loads(draft["result"])["draft"]
            dossier["listing"]["description"] = (
                "An English workbook with examples, exercises and worksheets. "
                "Verify the description against the included file before approval."
            )
        return memory.propose("publish", gumroad.publication(args.id, dossier), 0)

    is_chapter = args.command == "propose-chapter"
    limit = chapters.LIMIT if is_chapter else finance.OUTPUT_BILLING_BOUND
    prompt = chapters.prompt(dossier["evidence"]["topic"], args.chapter) if is_chapter else creator.prompt_for(dossier)
    if memory.mode == "simulation":
        model, commitment = "offline-simulation", 100
    else:
        model = required("CLAUDE_MODEL", r"[a-z0-9-]{5,100}")
        commitment = finance.claude_commitment(
            model,
            int(required("CLAUDE_INPUT_CENTS_PER_MILLION", r"[1-9][0-9]{0,4}")),
            int(required("CLAUDE_OUTPUT_CENTS_PER_MILLION", r"[1-9][0-9]{0,4}")),
            output_limit=limit,
        )
    payload = {"dossier_id": args.id, "model": model, "prompt": prompt,
               "max_tokens": limit}
    if is_chapter:
        payload["chapter"] = args.chapter
    return memory.propose("claude", payload, commitment)


def execute(args, memory, http):
    command = args.command
    live = memory.mode == "live"
    if command in {"artifact-review", "artifact-handoff"}:
        from pathlib import Path
        from .publication_review import request_review, handoff
        path = Path(args.file)
        with path.open("rb") as stream:
            data = stream.read(5_000_001)
        if command == "artifact-review":
            row = request_review(memory, args.dossier, path.name, data)
            return {key: row[key] for key in ("id", "digest", "expires_at", "payload")}
        return handoff(memory, args.approval, args.dossier, path.name, data)
    if command == "plan":
        source = GitHubResearch(http) if live else None
        return {"id": director.plan(memory, args.topic, args.price, args.unit_cost,
                                    args.fixed_cost, source)}
    if command == "show":
        return memory.load(args.id)
    if command == "approval":
        return memory.get(args.id)
    if command.startswith("propose-"):
        row = proposal(args, memory)
        return {field: row[field] for field in ("id", "kind", "digest", "max_cents", "expires_at")}
    if command == "simulate-decision":
        row = memory.get(args.id)
        memory.decide(args.id, row["digest"], args.verdict == "approve", "simulation")
    if command == "run-claude":
        client = Claude(http, required("ANTHROPIC_API_KEY")) if live else None
        payload = memory.claim(args.id, {"claude"})
        try:
            if client:
                result = client.generate(payload, lambda: memory.check_claim(args.id, {"claude"}))
            else:
                result = {"draft": "Offline draft. No Claude API call was made.",
                          "usage": {}, "model": payload["model"], "stop_reason": "end_turn"}
            memory.record_draft(args.id, result)
        except Exception as exc:
            memory.operation_failed(args.id, type(exc).__name__)
            raise
        if not live:
            memory.finish(args.id, 0, f"simulation:{args.id}")
        return {"id": args.id, "draft_saved": True, "complete_draft": result.get("stop_reason") == "end_turn",
                "reconciliation_required": live}
    if command == "claim":
        if live:
            raise Refused("Claim live manual operations in Telegram")
        return memory.claim(args.id, MANUAL_KINDS)
    if command == "serve":
        if not live:
            raise Refused("Permanent service requires live mode")
        if os.environ.get("BODIVE_WORKER_ENABLED") != "yes":
            raise Refused("Permanent service requires BODIVE_WORKER_ENABLED=yes")
        from .worker import serve
        operator = telegram(http)
        operator.poll_wait = 15
        serve(memory, operator)
        return {"ok": True}
    if command in {"poll", "notify"}:
        if not live:
            raise Refused("Telegram network calls require live mode")
        operator = telegram(http)
        if command == "poll":
            supervisor.poll(memory, operator)
        else:
            memory.check_running()
            supervisor.notify(memory, operator, args.id)
    if command in {"complete", "income"}:
        if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,240}", args.reference):
            raise Refused("Reference must be a receipt ID or URL without query parameters or personal data")
        if command == "complete":
            memory.finish(args.id, args.cents, args.reference)
        else:
            memory.income(args.cents, args.reference)
    if command == "stop":
        memory.stop("operator")
    if command == "resume":
        memory.resume()
    if command == "report":
        return memory.report()
    if command == "events":
        return memory.events()
    return {"ok": True}


def main():
    args = parser().parse_args()
    mode = os.environ.get("BODIVE_MODE", "simulation")
    try:
        if mode not in {"simulation", "live"}:
            raise Refused("BODIVE_MODE must be simulation or live")
        if mode == "live":
            if os.environ.get("BODIVE_LIVE_ENABLED") != "yes":
                raise Refused("Live mode requires BODIVE_LIVE_ENABLED=yes")
            location = required("SUPABASE_DATABASE_URL")
        else:
            location = os.environ.get("BODIVE_STATE_PATH", "state/bodive.sqlite")
        result = execute(args, Memory(mode, location), Http())
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Refused as exc:
        print(f"BODIVE: {exc}", file=sys.stderr)
    except Exception as exc:
        # Driver errors and malformed provider responses can contain secrets or private data.
        print(f"BODIVE: operation failed ({type(exc).__name__})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
