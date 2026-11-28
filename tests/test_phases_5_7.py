import unittest
from datetime import date
from unittest.mock import Mock
from io import BytesIO
from openpyxl import load_workbook
from bodive import performance, market_evidence, catalog
from bodive.memory import Refused

class CombinedTests(unittest.TestCase):
    def test_finance(self):
        m = Mock()
        m.report.return_value = {"available_cents": 0}
        result = performance.report(m)
        self.assertTrue(result["budget_exhausted"])
        self.assertIsNone(result["verified_sales"])
    def test_market(self):
        row = {"url":"https://example.com/product","observed":"2026-01-01","kind":"price","note":"Example only"}
        result = market_evidence.review([row], date(2026, 3, 1))
        self.assertTrue(result["records"][0]["expired"])
        self.assertFalse(result["demand_validated"])
        with self.assertRaises(Refused):
            market_evidence.review([row, row], date(2026, 3, 1))
    def test_catalog(self):
        m = Mock()
        for product in catalog.PRODUCTS:
            wb = load_workbook(BytesIO(catalog.generate(m, product)))
            self.assertEqual(wb.sheetnames, ["Tracker", "Review"])
        with self.assertRaises(Refused):
            catalog.generate(m, "unknown")
        m.check_running.side_effect = Refused("stopped")
        with self.assertRaises(Refused):
            catalog.generate(m, "habit_tracker")
