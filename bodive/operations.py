"""Aggregate operational status without exposing payloads or credentials."""
from .memory import now
from .local_queue import _jobs

def snapshot(memory):
    with memory.transaction() as query:
        stopped = bool(query("select stopped from control where id=1").fetchone()["stopped"])
        pending = query("select count(*) as total from approvals where status='pending' and expires_at>?", now().isoformat()).fetchone()["total"]
        products = query("select count(*) as total from opportunities").fetchone()["total"]
        queue = {}
        for job in _jobs(query).values():
            queue[job["state"]] = queue.get(job["state"], 0) + 1
        return {"stopped": stopped, "pending_approvals": pending, "dossiers": products,
                "queue": queue, "committed_cents": memory.reserved(query, now().isoformat()),
                "budget_cents": 10000}
