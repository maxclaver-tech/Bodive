"""Offline publication review primitives. Never publish or contact a provider."""
from hashlib import sha256
from hmac import compare_digest
import re

from .memory import Refused


def review_scope(dossier_id, filename, data):
    if not isinstance(dossier_id, str) or not re.fullmatch(r"[0-9a-f]{32}", dossier_id):
        raise Refused("Invalid dossier")
    if not isinstance(filename, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}\.(xlsx|pdf|zip)", filename):
        raise Refused("Invalid filename")
    if type(data) is not bytes or not 0 < len(data) <= 5_000_000:
        raise Refused("Invalid artifact")
    return {"dossier_id": dossier_id, "filename": filename,
            "sha256": sha256(data).hexdigest(), "size": len(data),
            "purpose": "manual_publication_review"}


def verify_artifact(scope, dossier_id, filename, data):
    """Check exact reviewed bytes; this is NOT an authorization check."""
    actual = review_scope(dossier_id, filename, data)
    if not isinstance(scope, dict) or set(scope) != set(actual):
        raise Refused("Invalid review scope")
    digest = scope.get("sha256")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise Refused("Invalid digest")
    if not compare_digest(digest, actual["sha256"]) or any(
        scope[k] != actual[k] for k in actual if k != "sha256"
    ):
        raise Refused("Artifact changed; new review required")
    return actual


def request_review(memory, dossier_id, filename, data):
    memory.load(dossier_id)
    return memory.propose("publish", review_scope(dossier_id, filename, data), 0)


def handoff(memory, identifier, dossier_id, filename, data):
    """Consume an independent approval only after exact-byte verification."""
    import json
    from .memory import now
    with memory.transaction() as query:
        memory.require_running(query)
        timestamp = now().isoformat()
        row = query("select * from approvals where id=? and kind='publish' "
                    "and status='approved' and blocked=0 and expires_at>?",
                    identifier, timestamp).fetchone()
        if row is None:
            raise Refused("No active publication approval")
        scope = verify_artifact(json.loads(row["payload"]), dossier_id, filename, data)
        query("update approvals set status='claimed', claimed_at=? where id=?",
              timestamp, identifier)
        memory.audit(query, "manual_publication_handoff", id=identifier,
                     sha256=scope["sha256"])
        return {"approval_id": identifier, "artifact": scope,
                "status": "manual_handoff_only", "published": False}
