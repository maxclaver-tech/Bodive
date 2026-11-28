import unittest
from unittest.mock import Mock
from bodive.marketing import campaign
from bodive.memory import Refused

class MarketingTests(unittest.TestCase):
    def test_preview(self):
        memory = Mock()
        memory.load.return_value = {"evidence": {"topic": "Personal budget spreadsheet"}}
        for language in ("es", "en"):
            result = campaign(memory, "test", language, "2026-12-01")
            self.assertFalse(result["published"])
            self.assertFalse(result["scheduled"])
            self.assertEqual(result["budget_cents"], 0)
            self.assertIsNone(result["metrics"]["sales"])
            self.assertEqual([x["date"] for x in result["items"]], ["2026-12-01", "2026-12-04", "2026-12-07"])
            self.assertTrue(all(x["review_required"] for x in result["items"]))
        with self.assertRaises(Refused):
            campaign(memory, "test", "es", "invalid")
        memory.check_running.side_effect = Refused("stopped")
        with self.assertRaises(Refused):
            campaign(memory, "test", "es", "2026-12-01")
