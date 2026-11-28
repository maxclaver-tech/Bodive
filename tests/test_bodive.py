import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from bodive import cli, director, finance, supervisor
from bodive.connectors import Claude, GitHubResearch
from bodive.memory import Memory, Refused


class MemoryContract:
    def approve(self, row):
        self.memory.decide(row["id"], row["digest"], True, "telegram:42")

    def test_concurrent_budget_and_no_replenishment_from_income(self):
        rows = [self.memory.propose("expense", {"vendor": str(i)}, 6000) for i in range(2)]

        def attempt(row):
            try:
                self.approve(row)
                return row["id"]
            except Refused:
                return None

        with ThreadPoolExecutor(2) as pool:
            winners = [identifier for identifier in pool.map(attempt, rows) if identifier]
        self.assertEqual(len(winners), 1)
        self.memory.claim(winners[0], {"expense"})
        with self.assertRaises(Refused):
            self.memory.finish(winners[0], 6001, "receipt-1")
        self.memory.finish(winners[0], 5500, "receipt-1")
        self.memory.income(7000, "payout-1")
        with self.assertRaises(Refused):
            self.memory.income(7000, "payout-1")
        self.assertEqual(self.memory.report()["available_cents"], 4500)
        self.assertEqual(self.memory.report()["profit_cents"], 1500)

    def test_stop_invalidates_claims_even_after_resume(self):
        active = self.memory.propose("expense", {"vendor": "x"}, 400)
        pending = self.memory.propose("publish", {}, 0)
        self.approve(active)
        self.memory.claim(active["id"], {"expense"})
        self.memory.stop("test")
        with self.assertRaises(Refused):
            self.memory.propose("publish", {}, 0)
        self.memory.resume()
        self.assertEqual(self.memory.get(pending["id"])["status"], "cancelled")
        with self.assertRaises(Refused):
            self.memory.check_claim(active["id"], {"expense"})
        self.assertEqual(self.memory.report()["committed_cents"], 400)
        self.memory.finish(active["id"], 0, "void:confirmed")
        self.assertEqual(self.memory.report()["committed_cents"], 0)

    def test_approval_digest_expiry_and_replay(self):
        row = self.memory.propose("publish", {"price": 1200}, 0)
        with self.assertRaises(Refused):
            self.memory.decide(row["id"], "0" * 64, True, "telegram:42")
        self.approve(row)
        with self.assertRaises(Refused):
            self.approve(row)
        with self.memory.transaction() as query:
            query("update approvals set expires_at=? where id=?", "2000-01-01", row["id"])
        with self.assertRaises(Refused):
            self.memory.claim(row["id"], {"publish"})

    def test_api_attempts_consume_quota_and_keep_reservation(self):
        for _ in range(3):
            row = self.memory.propose("claude", {}, 200)
            self.approve(row)
            self.memory.claim(row["id"], {"claude"})
            self.memory.operation_failed(row["id"], "TimeoutError")
            with self.assertRaises(Refused):
                self.memory.claim(row["id"], {"claude"})
        row = self.memory.propose("claude", {}, 200)
        self.approve(row)
        with self.assertRaisesRegex(Refused, "quota"):
            self.memory.claim(row["id"], {"claude"})
        self.assertEqual(self.memory.report()["committed_cents"], 800)


class SQLiteTests(MemoryContract, unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.memory = Memory("simulation", Path(directory.name) / "db.sqlite")

    def test_end_to_end_cli_offline(self):
        env = {**os.environ, "BODIVE_MODE": "simulation", "BODIVE_STATE_PATH": str(self.memory.location)}

        def run(*args):
            return json.loads(subprocess.check_output([sys.executable, "-m", "bodive.cli", *args], env=env))

        identifier = run("plan", "Client onboarding")["id"]
        dossier = run("show", identifier)
        self.assertEqual(dossier["evidence"]["observations"], [])
        self.assertIn("Unverified", dossier["analysis"]["demand"])
        self.assertIn("Client Onboarding", dossier["product_markdown"])
        draft = run("propose-claude", identifier)["id"]
        run("simulate-decision", draft, "approve")
        run("run-claude", draft)
        publication = run("propose-publish", identifier)["id"]
        run("simulate-decision", publication, "approve")
        self.assertEqual(run("claim", publication)["listing"]["price_cents"], 1200)
        run("complete", publication, "0", "https://example.invalid/product")
        self.assertEqual(run("report")["expenses_cents"], 0)

    def test_incomplete_draft_cannot_be_published(self):
        identifier = director.plan(self.memory, "onboarding", 1200, 400, 0, None)
        row = self.memory.propose("claude", {"dossier_id": identifier}, 208)
        self.approve(row)
        self.memory.claim(row["id"], {"claude"})
        self.memory.record_draft(row["id"], {"draft": "Partial", "stop_reason": "max_tokens"})
        self.memory.finish(row["id"], 1, "test-receipt")
        args = cli.parser().parse_args(["propose-publish", identifier, "--draft-id", row["id"]])
        with self.assertRaises(Refused):
            cli.proposal(args, self.memory)

    def test_telegram_filters_and_persists_offset(self):
        row = self.memory.propose("publish", {}, 0)
        telegram = Mock(operator=42)
        command = f"/approve {row['id']} {row['digest']}"
        base = {"text": command, "chat": {"type": "private", "id": 42}}
        telegram.updates.return_value = [
            {"update_id": 10, "message": {**base, "from": {"id": 41, "is_bot": False}}},
            {"update_id": 11, "message": {**base, "from": {"id": 42, "is_bot": False},
                                          "forward_origin": {}}},
        ]
        supervisor.poll(self.memory, telegram)
        self.assertEqual(self.memory.get(row["id"])["status"], "pending")
        telegram.send.assert_not_called()
        telegram.updates.return_value = [
            {"update_id": 12, "message": {**base, "from": {"id": 42, "is_bot": False}}},
        ]
        supervisor.poll(self.memory, telegram)
        telegram.updates.assert_called_with(12)
        self.assertEqual(self.memory.get(row["id"])["decided_by"], "telegram:42")
        self.assertEqual(self.memory.offset(), 13)

    def test_live_research_attribution_and_quota(self):
        http = Mock()
        http.request.return_value = {"items": [{"html_url": "https://github.com/test/repo",
                                               "full_name": "test/repo", "stargazers_count": 123,
                                               "updated_at": "2026-11-01T00:00:00Z"}],
                                     "incomplete_results": False}
        for _ in range(30):
            identifier = director.plan(self.memory, "onboarding", 1200, 400, 800, GitHubResearch(http))
        with self.assertRaises(Refused):
            director.plan(self.memory, "onboarding", 1200, 400, 800, GitHubResearch(http))
        dossier = self.memory.load(identifier)
        self.assertEqual(dossier["analysis"]["break_even_units"], 1)
        self.assertEqual(dossier["evidence"]["observations"][0]["stars"], 123)
        self.assertEqual(http.request.call_count, 12)

@unittest.skipUnless(os.environ.get("BODIVE_TEST_POSTGRES"), "requires disposable PostgreSQL")
class PostgresTests(MemoryContract, unittest.TestCase):
    def setUp(self):
        import psycopg

        dsn = os.environ["BODIVE_TEST_POSTGRES"]
        self.assertIn(psycopg.conninfo.conninfo_to_dict(dsn).get("host", ""),
                      ("localhost", "127.0.0.1", ""), "tests reset the local bodive schema")
        self.assertEqual(os.environ.get("BODIVE_TEST_POSTGRES_RESET"), "yes",
                         "explicitly allow resetting the disposable test schema")
        connect = psycopg.connect

        def connect_local(*args, **kwargs):
            return connect(*args, **{**kwargs, "sslmode": "disable"})

        with connect_local(dsn, autocommit=True) as connection:
            connection.execute("drop schema if exists bodive cascade")
            for role in ("anon", "authenticated", "service_role"):
                connection.execute(f"do $$ begin create role {role}; "
                                   "exception when duplicate_object then null; end $$")
            migration = Path("supabase/migrations/202611270001_bodive.sql").read_text()
            connection.execute(migration)
        self.memory = Memory("live", dsn)
        patcher = patch("psycopg.connect", side_effect=lambda *args, **kwargs:
                        connect_local(*args, **kwargs, options="-c role=bodive_runner"))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_live_rejects_local_decision(self):
        row = self.memory.propose("publish", {}, 0)
        with self.assertRaisesRegex(Refused, "Telegram"):
            self.memory.decide(row["id"], row["digest"], True, "simulation")


class ProviderTests(unittest.TestCase):
    def test_claude_refuses_large_request(self):
        http = Mock()
        http.request.return_value = {"input_tokens": 4001}
        with self.assertRaises(Refused):
            Claude(http, "test-key").generate({"model": "x", "prompt": "x"}, Mock())
        self.assertEqual(http.request.call_count, 1)
        self.assertTrue(http.request.call_args.args[1].endswith("/count_tokens"))

    def test_claude_send_body_and_draft(self):
        http = Mock()
        http.request.side_effect = [{"input_tokens": 50}, {"model": "x", "usage": {"output_tokens": 3},
                                   "stop_reason": "end_turn", "content": [{"type": "text", "text": "Draft"}]}]
        check = Mock()
        draft = Claude(http, "test-key").generate({"model": "x", "prompt": "x"}, check)
        self.assertEqual(draft["draft"], "Draft")
        self.assertEqual(check.call_count, 2)
        self.assertEqual(http.request.call_args.args[2]["max_tokens"], 1600)

    def test_new_limit_is_explicit_and_legacy_is_unchanged(self):
        for limit in (1600, 8000):
            http = Mock()
            http.request.side_effect = [{"input_tokens": 50}, {"model": "x", "usage": {},
                "stop_reason": "max_tokens", "content": [{"type": "text", "text": "Partial"}]}]
            payload = {"model": "x", "prompt": "x", "max_tokens": limit}
            result = Claude(http, "test-key").generate(payload, Mock())
            self.assertEqual(http.request.call_args.args[2]["max_tokens"], limit)
            self.assertEqual(result["stop_reason"], "max_tokens")

    def test_spend_floor_and_rounded_reservation(self):
        model = "claude-haiku-4-5-20251001"
        self.assertEqual(finance.claude_commitment(model, 200, 1000), 208)
        with self.assertRaises(Refused):
            finance.claude_commitment(model, 100, 1000)

    def test_live_requires_activation_before_database_access(self):
        with patch.dict(os.environ, {"BODIVE_MODE": "live", "BODIVE_LIVE_ENABLED": "no"}):
            with patch.object(sys, "argv", ["bodive", "report"]), patch("bodive.cli.Memory") as memory:
                with patch("sys.stderr"):
                    self.assertEqual(cli.main(), 1)
                memory.assert_not_called()
