import unittest
from unittest.mock import patch
from bodive.diagnostics import category


class OperationalError(Exception):
    pass


class DiagnosticsTests(unittest.TestCase):
    @patch.dict("os.environ", {"PGSSLROOTCERT": ""})
    def test_fixed_labels_never_expose_secret(self):
        for message, expected in (
            ("password authentication failed: SECRET", "DB_AUTH_FAILED"),
            ("certificate verify failed: SECRET", "DB_TLS_VERIFY_FAILED"),
            ("Tenant or user not found SECRET", "DB_USER_OR_PROJECT_INVALID"),
            ("connection timed out SECRET", "DB_CONNECT_TIMEOUT"),
            ("unknown failure SECRET", "DB_OPERATIONAL_ERROR"),
        ):
            self.assertEqual(category(OperationalError(message)), expected)

    @patch.dict("os.environ", {"PGSSLROOTCERT": "/nonexistent/bodive-ca.crt"})
    def test_missing_certificate(self):
        self.assertEqual(category(OperationalError("SECRET")), "DB_CA_FILE_MISSING")
