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
