"""Classify failures into fixed public labels; never return exception text."""
import os
from pathlib import Path


def category(exc):
    if type(exc).__name__ != "OperationalError":
        return type(exc).__name__
    message = str(exc).casefold()
    cert = os.environ.get("PGSSLROOTCERT")
    if cert and not Path(cert).is_file():
        return "DB_CA_FILE_MISSING"
    rules = (
        (("password authentication failed", "authentication failed", "sasl authentication"), "DB_AUTH_FAILED"),
        (("tenant or user not found", "role does not exist", "user not found"), "DB_USER_OR_PROJECT_INVALID"),
        (("certificate verify failed", "certificate verification", "does not match host name", "certificate has expired"), "DB_TLS_VERIFY_FAILED"),
        (("root certificate", "could not read certificate", "could not load certificate"), "DB_CA_FILE_INVALID"),
        (("could not translate host name", "name or service not known", "temporary failure in name resolution"), "DB_DNS_FAILED"),
        (("timeout expired", "connection timed out", "connection timeout"), "DB_CONNECT_TIMEOUT"),
        (("network is unreachable", "no route to host", "connection refused"), "DB_NETWORK_FAILED"),
        (("max client connections", "too many connections", "remaining connection slots"), "DB_CONNECTION_LIMIT"),
        (("invalid connection option", "invalid uri", "missing \"=\"", "invalid percent-encoded"), "DB_DSN_INVALID"),
    )
    for patterns, label in rules:
        if any(pattern in message for pattern in patterns):
            return label
    return "DB_OPERATIONAL_ERROR"
