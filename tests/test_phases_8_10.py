import unittest
from tempfile import TemporaryDirectory
from pathlib import Path
from bodive.memory import Memory, Refused
from bodive.optimization import scenarios
from bodive.local_queue import enqueue, claim, resolve
from bodive.operations import snapshot

class FinalPhases(unittest.TestCase):
    def test_pricing(self):
        result = scenarios([1000], 10, 1000, 1000, 100)
        self.assertEqual(result["rows"][0]["hypothetical_profit_cents"], 7000)
        self.assertEqual(result["rows"][0]["break_even_units"], 2)
        self.assertFalse(result["external_changes"])
    def test_queue(self):
        with TemporaryDirectory() as folder:
            path = str(Path(folder)/"db.sqlite")
            m = Memory("simulation", path)
            enqueue(m, "low", "finance", 1)
            enqueue(m, "high", "pricing_review", 9)
            enqueue(m, "high", "pricing_review", 9)
            with self.assertRaises(Refused):
                enqueue(m, "high", "finance", 9)
            m = Memory("simulation", path)
            self.assertEqual(claim(m)["id"], "high")
            with self.assertRaises(Refused):
                claim(m)
            m.stop("test")
            with self.assertRaises(Refused):
                resolve(m, "high", "completed")
            resolve(m, "high", "failed")
            self.assertEqual(snapshot(m)["queue"], {"pending":1,"failed":1})
            self.assertTrue(snapshot(m)["stopped"])
