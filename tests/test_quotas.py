import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import timedelta
from bodive.memory import Memory, Refused, now


class QuotaTests(unittest.TestCase):
    def test_isolated_limits_and_atomic_batch(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            for _ in range(29):
                m.research_slot()
            with self.assertRaises(Refused):
                m.research_slot("market",4)
            self.assertEqual(m.research_status()["market"]["used"],29)
            m.research_slot()
            with self.assertRaises(Refused):
                m.research_slot()
            for _ in range(20):
                m.research_slot("catalog")
            with self.assertRaises(Refused):
                m.research_slot("catalog")
            m.research_slot("daily",4)
            with self.assertRaises(Refused):
                m.research_slot("daily")
            self.assertEqual(m.report()["committed_cents"],0)
            with patch("bodive.memory.now",return_value=now()+timedelta(days=1)):
                self.assertEqual(m.research_status()["market"]["used"],0)
                m.research_slot("catalog")
            m.stop("test")
            with self.assertRaises(Refused):
                m.research_slot("daily")

    def test_legacy_events_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            with m.transaction() as query:
                m.audit(query,"research_started")
            self.assertEqual(m.research_status()["market"]["used"],1)
            self.assertEqual(m.research_status()["catalog"]["used"],0)
