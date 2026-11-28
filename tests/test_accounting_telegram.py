import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from bodive import director, supervisor
from bodive.memory import Memory, Refused


class AccountingTelegramTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.memory = Memory("simulation", Path(tmp.name)/"db.sqlite")
        self.telegram = Mock(operator=42)
        self.dossier = director.plan(self.memory, "onboarding", 1200, 400, 0, None)
        self.row = self.memory.propose("claude", {"dossier_id":self.dossier,"chapter":1},203)
        self.memory.decide(self.row["id"], self.row["digest"], True, "telegram:42")
        self.memory.claim(self.row["id"], {"claude"})

    def send(self, command, sender=42):
        return supervisor.on_message(self.memory, self.telegram, {
            "text":command, "chat":{"type":"private","id":42},
            "from":{"id":sender,"is_bot":False}})

    def test_explicit_reconciliation_and_replay(self):
        identifier = self.row["id"]
        self.send(f"/reconcile {identifier} 1 receipt")
        self.send(f"/reconcile {identifier} 1 receipt CONFIRMO", sender=41)
        self.assertEqual(self.memory.get(identifier)["status"],"claimed")
        self.send("/pending")
        self.send(f"/reconcile {identifier} 1 receipt CONFIRMO")
        self.assertEqual(self.memory.get(identifier)["status"],"done")
        self.assertEqual(self.memory.report()["expenses_cents"],1)
        self.assertEqual(self.memory.product_report(self.dossier)["cost_cents"],1)
        with self.assertRaises(Refused):
            self.send(f"/reconcile {identifier} 1 receipt CONFIRMO")

    def test_zero_receipt_and_hosting_duplicate(self):
        identifier = self.row["id"]
        self.send(f"/reconcile {identifier} 0 rejected401 CONFIRMO")
        self.assertEqual(self.memory.report()["committed_cents"],0)
        self.send("/hosting 800 render-nov CONFIRMO")
        self.assertEqual(self.memory.report()["expenses_cents"],800)
        with self.assertRaises(Refused):
            self.send("/hosting 800 render-nov CONFIRMO")

    def test_hosting_over_budget_stops(self):
        self.send("/hosting 10000 invoice CONFIRMO")
        with self.assertRaises(Refused):
            self.memory.check_running()
        self.assertEqual(self.memory.report()["expenses_cents"],10000)
        self.assertEqual(self.memory.get(self.row["id"])["blocked"],1)
