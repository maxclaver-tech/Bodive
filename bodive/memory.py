"""Transactional memory, audit log, and approvals for both storage backends."""

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

BUDGET_CENTS = 10_000
MANUAL_KINDS = {"publish", "advertise", "expense"}


class Refused(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def now():
    return datetime.now(UTC)


class Memory:
    def __init__(self, mode, location):
        self.mode = mode
        self.location = location

    @contextmanager
    def transaction(self):
        if self.mode == "live":
            import psycopg
            from psycopg.rows import dict_row

            conn = psycopg.connect(
                self.location, row_factory=dict_row,
                connect_timeout=8, sslmode="verify-full",
            )
        else:
            path = Path(self.location)
            path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("pragma foreign_keys=on")
            conn.executescript(Path(__file__).with_name("schema.sql").read_text())

        def query(sql, *args):
            return conn.execute(sql.replace("?", "%s") if self.mode == "live" else sql, args)

        try:
            with conn:
                if self.mode == "live":
                    query("set local search_path = bodive")
                    query("set local statement_timeout = '10s'")
                # Serialize all budget, approval, and stop changes across runners.
                query("update control set stopped=stopped where id=1")
                yield query
        finally:
            conn.close()

    @contextmanager
    def poll_lock(self):
        # A session-level PostgreSQL lock spans network I/O without holding the
        # budget transaction open. All live polling entry points use this lock.
        if self.mode != "live":
            yield True
            return
        import psycopg
        with psycopg.connect(self.location, autocommit=True, connect_timeout=8,
                             sslmode="verify-full") as conn:
            acquired = conn.execute("select pg_try_advisory_lock(183520114, 91731)").fetchone()[0]
            try:
                yield acquired
            finally:
                if acquired:
                    conn.execute("select pg_advisory_unlock(183520114, 91731)")

    def audit(self, query, name, **detail):
        query("insert into events values (?, ?, ?, ?)", uuid4().hex, now().isoformat(),
              name, canonical(detail))

    def require_running(self, query):
        if query("select stopped from control where id=1").fetchone()["stopped"]:
            raise Refused("Emergency stop is active")

    def check_running(self):
        with self.transaction() as query:
            self.require_running(query)

    def stop(self, actor):
        with self.transaction() as query:
            query("update control set stopped=1 where id=1")
            query("update approvals set status='cancelled' where status in ('pending','approved')")
            query("update approvals set blocked=1 where status='claimed'")
            self.audit(query, "emergency_stop", actor=actor)

    def resume(self):
        with self.transaction() as query:
            query("update control set stopped=0 where id=1")
            self.audit(query, "resume", actor="operator")

    def research_slot(self):
        with self.transaction() as query:
            self.require_running(query)
            since = now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
            count = query("select count(*) as total from events where name='research_started' "
                          "and created_at>=?", since).fetchone()["total"]
            if count >= 12:
                raise Refused("Research quota reached for the UTC day")
            self.audit(query, "research_started")

    def operation_failed(self, identifier, error_type):
        with self.transaction() as query:
            self.audit(query, "operation_failed", id=identifier, error_type=error_type)

    def save(self, dossier):
        identifier = uuid4().hex
        with self.transaction() as query:
            self.require_running(query)
            query("insert into opportunities values (?, ?, ?)",
                  identifier, now().isoformat(), canonical(dossier))
            self.audit(query, "dossier_saved", id=identifier)
        return identifier

    def load(self, identifier):
        with self.transaction() as query:
            row = query("select dossier from opportunities where id=?", identifier).fetchone()
            if row is None:
                raise Refused("Unknown dossier")
            return json.loads(row["dossier"])

    def propose(self, kind, payload, cents):
        if (kind not in MANUAL_KINDS | {"claude"} or type(cents) is not int
                or not 0 <= cents <= BUDGET_CENTS
                or (kind in {"claude", "expense"} and cents == 0)
                or (kind == "publish" and cents != 0)):
            raise Refused("Invalid operation or EUR commitment")
        identifier = uuid4().hex
        encoded = canonical(payload)
        digest = hashlib.sha256(canonical([identifier, kind, cents, payload]).encode()).hexdigest()
        timestamp = now()
        with self.transaction() as query:
            self.require_running(query)
            query("""insert into approvals
                  (id,kind,payload,digest,created_at,expires_at,max_cents,status)
                  values (?,?,?,?,?,?,?,'pending')""",
                  identifier, kind, encoded, digest, timestamp.isoformat(),
                  (timestamp + timedelta(hours=24)).isoformat(), cents)
            self.audit(query, "approval_requested", id=identifier, kind=kind, cents=cents)
        return self.get(identifier)

    def get(self, identifier):
        with self.transaction() as query:
            row = query("select * from approvals where id=?", identifier).fetchone()
            if row is None:
                raise Refused("Unknown approval")
            return dict(row)

    def decide(self, identifier, digest, approve, actor):
        if self.mode == "live" and not actor.startswith("telegram:"):
            raise Refused("Live decisions require Telegram")
        with self.transaction() as query:
            self.require_running(query)
            timestamp = now().isoformat()
            row = query("select * from approvals where id=? and digest=? and status='pending' "
                        "and expires_at>?", identifier, digest, timestamp).fetchone()
            if row is None:
                raise Refused("Unknown, expired or already decided approval")
            if approve:
                reserved = self.reserved(query, timestamp)
                if reserved + row["max_cents"] > BUDGET_CENTS:
                    raise Refused("Approval would exceed the EUR 100 budget")
            verdict = "approved" if approve else "rejected"
            query("update approvals set status=?, decided_by=? where id=?", verdict, actor, identifier)
            self.audit(query, verdict, id=identifier, actor=actor)

    def reserved(self, query, timestamp):
        return query("""select coalesce(sum(max_cents),0) as total from approvals
                     where status='claimed' or (status='approved' and expires_at>?)""",
                     timestamp).fetchone()["total"] + query(
            "select coalesce(sum(cents),0) as total from ledger where kind='expense'"
        ).fetchone()["total"]

    def claim(self, identifier, kinds):
        with self.transaction() as query:
            self.require_running(query)
            timestamp = now()
            row = query("select * from approvals where id=? and status='approved' and expires_at>?",
                        identifier, timestamp.isoformat()).fetchone()
            if row is None or row["kind"] not in kinds:
                raise Refused("Operation lacks a current approval of the required type")
            if row["kind"] == "claude":
                since = timestamp.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
                counts = query("""select count(*) as lifetime,
                               count(case when claimed_at>=? then 1 end) as today
                               from approvals where kind='claude' and claimed_at is not null""",
                               since).fetchone()
                if counts["today"] >= 3 or counts["lifetime"] >= 20:
                    raise Refused("Claude request quota reached")
            query("update approvals set status='claimed', claimed_at=? where id=?",
                  timestamp.isoformat(), identifier)
            self.audit(query, "operation_claimed", id=identifier)
            return json.loads(row["payload"])

    def check_claim(self, identifier, kinds):
        with self.transaction() as query:
            self.require_running(query)
            row = query("select kind,expires_at from approvals where id=? and status='claimed' "
                        "and blocked=0", identifier).fetchone()
            if row is None or row["kind"] not in kinds or row["expires_at"] <= now().isoformat():
                raise Refused("Claim is inactive or expired")

    def record_draft(self, identifier, draft):
        with self.transaction() as query:
            count = query("update approvals set result=? where id=? and kind='claude' "
                          "and status='claimed' and result is null", canonical(draft), identifier).rowcount
            if count != 1:
                raise Refused("Draft could not be attached to the claim")
            self.audit(query, "claude_draft_saved", id=identifier)

    def record_discovery(self, snapshot):
        identifier = uuid4().hex
        with self.transaction() as query:
            self.require_running(query)
            self.audit(query, "discovery_snapshot", discovery_id=identifier, snapshot=snapshot)
        return identifier

    def get_discovery(self, identifier=None):
        with self.transaction() as query:
            for row in query("select detail from events where name='discovery_snapshot' order by created_at desc"):
                detail = json.loads(row["detail"])
                if identifier is None or detail.get("discovery_id")==identifier:
                    return detail
        return None

    def record_community(self, identifier, result):
        with self.transaction() as query:
            self.require_running(query)
            if query("select id from opportunities where id=?", identifier).fetchone() is None:
                raise Refused("Unknown dossier")
            self.audit(query, "community_snapshot", dossier_id=identifier, snapshot=result)

    def latest_community(self, identifier):
        with self.transaction() as query:
            for row in query("select detail from events where name='community_snapshot' order by created_at desc"):
                detail = json.loads(row["detail"])
                if detail.get("dossier_id")==identifier:
                    return detail["snapshot"]
        return None

    def market_observation(self, identifier, kind, url, note, actor):
        from .market import observation
        if self.mode == "live" and not actor.startswith("telegram:"):
            raise Refused("Live market observations require Telegram")
        item = observation(kind, url, note)
        with self.transaction() as query:
            self.require_running(query)
            if query("select id from opportunities where id=?", identifier).fetchone() is None:
                raise Refused("Unknown dossier")
            self.audit(query, "market_observation", dossier_id=identifier, observation=item, actor=actor)

    def market_observations(self, identifier):
        with self.transaction() as query:
            return [detail["observation"] for row in query(
                "select detail from events where name='market_observation' order by created_at")
                    if (detail := json.loads(row["detail"])).get("dossier_id")==identifier]

    def pending_costs(self):
        with self.transaction() as query:
            return [dict(row) for row in query(
                "select id,kind,max_cents,claimed_at,result from approvals "
                "where status='claimed' order by claimed_at limit 50")]

    def hosting_cost(self, cents, reference, actor):
        # Record an already incurred invoice, not a new purchase. Do not hide
        # an actual expense even if it takes the budget over its ceiling.
        if (type(cents) is not int or not 1 <= cents <= BUDGET_CENTS
                or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", reference)):
            raise Refused("Importe o referencia de alojamiento no válido")
        if self.mode == "live" and not actor.startswith("telegram:"):
            raise Refused("Live accounting requires Telegram")
        with self.transaction() as query:
            self.ledger_entry(query, "hosting:"+reference, "expense", cents, None)
            self.audit(query, "hosting_recorded", cents=cents, reference=reference, actor=actor)
            if self.reserved(query, now().isoformat()) > BUDGET_CENTS:
                query("update control set stopped=1 where id=1")
                query("update approvals set status='cancelled' where status in ('pending','approved')")
                query("update approvals set blocked=1 where status='claimed'")
                self.audit(query, "emergency_stop", actor=actor, reason="budget_exceeded")

    def product_report(self, identifier):
        with self.transaction() as query:
            row = query("select dossier from opportunities where id=?", identifier).fetchone()
            if row is None:
                raise Refused("Unknown dossier")
            dossier = json.loads(row["dossier"])
            costs = 0
            held = 0
            completed = set()
            timestamp = now().isoformat()
            for item in query("select a.*, l.cents as actual_cents from approvals a "
                              "left join ledger l on a.id=l.approval_id and l.kind='expense'"):
                payload = json.loads(item["payload"])
                if payload.get("dossier_id") != identifier:
                    continue
                costs += item["actual_cents"] or 0
                if item["status"] == "claimed" or (item["status"] == "approved" and item["expires_at"] > timestamp):
                    held += item["max_cents"]
                result = json.loads(item["result"] or "{}")
                if (item["kind"] == "claude" and not item["blocked"]
                        and result.get("stop_reason") == "end_turn"
                        and type(payload.get("chapter")) is int):
                    completed.add(payload["chapter"])
            return {"topic": dossier["evidence"]["topic"], "cost_cents":costs,
                    "reserved_cents":held, "completed_chapters":sorted(completed)}

    def finish(self, identifier, cents, reference, actor=None):
        with self.transaction() as query:
            row = query("select * from approvals where id=? and status='claimed'", identifier).fetchone()
            if row is None or type(cents) is not int or not 0 <= cents <= row["max_cents"]:
                raise Refused("Unknown claim or cost exceeds approved amount")
            if row["kind"] == "publish" and not reference.startswith(("https://", "void:")):
                raise Refused("Use the published URL or a void reference after confirming no publication")
            if actor is not None:
                if self.mode == "live" and not actor.startswith("telegram:"):
                    raise Refused("Live accounting requires Telegram")
                if row["kind"] != "claude":
                    raise Refused("Telegram reconciliation is limited to Claude")
                if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", reference):
                    raise Refused("Invalid receipt reference")
                reference = "claude:" + reference
            if cents or actor is not None:
                self.ledger_entry(query, reference, "expense", cents, identifier)
            query("update approvals set status='done', result=coalesce(result,?) where id=?",
                  canonical({"reference": reference}), identifier)
            self.audit(query, "operation_completed", id=identifier, cents=cents, reference=reference, actor=actor or "cli")

    def ledger_entry(self, query, reference, kind, cents, identifier):
        count = query("insert into ledger values (?, ?, ?, ?, ?) on conflict (reference) do nothing",
                      reference, kind, cents, identifier, now().isoformat()).rowcount
        if count != 1:
            raise Refused("Reference already recorded")

    def income(self, cents, reference):
        if type(cents) is not int or cents <= 0:
            raise Refused("Income must be positive")
        with self.transaction() as query:
            self.ledger_entry(query, reference, "income", cents, None)
            self.audit(query, "income_recorded", reference=reference, cents=cents)

    def report(self):
        with self.transaction() as query:
            totals = {row["kind"]: row["total"] for row in query(
                "select kind, sum(cents) as total from ledger group by kind")}
            income = totals.get("income", 0)
            expense = totals.get("expense", 0)
            reserved = self.reserved(query, now().isoformat())
            return {"budget_cents": BUDGET_CENTS, "income_cents": income,
                    "expenses_cents": expense, "profit_cents": income - expense,
                    "committed_cents": reserved, "available_cents": BUDGET_CENTS - reserved}

    def offset(self, next_offset=None):
        with self.transaction() as query:
            if next_offset is not None:
                query("update control set telegram_offset=? where id=1 and telegram_offset<?",
                      next_offset, next_offset)
            return query("select telegram_offset from control where id=1").fetchone()["telegram_offset"]

    def events(self):
        with self.transaction() as query:
            return [dict(row) for row in query("select * from events order by created_at desc limit 50")]
