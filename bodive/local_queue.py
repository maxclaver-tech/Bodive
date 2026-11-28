"""Persistent supervised queue using existing transactional audit events."""
import json
import re
from .memory import Refused, now

KINDS = {"finance", "research_review", "catalog_review", "pricing_review"}

def _jobs(query):
    jobs = {}
    for row in query("select detail from events where name='local_queue_state' order by created_at,id"):
        job = json.loads(row["detail"])
        jobs[job["id"]] = job
    return jobs

def enqueue(memory, identifier, kind, priority):
    if not isinstance(identifier, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", identifier) or kind not in KINDS or type(priority) is not int or not 0 <= priority <= 9:
        raise Refused("Invalid queue request")
    with memory.transaction() as query:
        memory.require_running(query)
        jobs = _jobs(query)
        if identifier in jobs:
            old = jobs[identifier]
            if old["kind"] != kind or old["priority"] != priority:
                raise Refused("Idempotency conflict")
            return old
        if len(jobs) >= 1000 or sum(j["state"] in {"pending","claimed"} for j in jobs.values()) >= 20:
            raise Refused("Queue capacity reached")
        job = {"id": identifier, "kind": kind, "priority": priority, "state": "pending", "created": now().isoformat()}
        memory.audit(query, "local_queue_state", **job)
        return job

def claim(memory):
    with memory.transaction() as query:
        memory.require_running(query)
        jobs = _jobs(query)
        if any(j["state"] == "claimed" for j in jobs.values()):
            raise Refused("Resolve existing claim first")
        pending = sorted((j for j in jobs.values() if j["state"] == "pending"), key=lambda j: (-j["priority"], j["created"], j["id"]))
        if not pending:
            return None
        job = {**pending[0], "state": "claimed"}
        memory.audit(query, "local_queue_state", **job)
        return job

def resolve(memory, identifier, outcome):
    if outcome not in {"completed", "failed", "cancelled"}:
        raise Refused("Invalid resolution")
    with memory.transaction() as query:
        jobs = _jobs(query)
        job = jobs.get(identifier)
        if not job or job["state"] != "claimed":
            raise Refused("No active claim")
        if outcome == "completed":
            memory.require_running(query)
        job = {**job, "state": outcome}
        memory.audit(query, "local_queue_state", **job)
        return job
