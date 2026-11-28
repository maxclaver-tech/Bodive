import unittest
from bodive.reconciliation import preview

class ReconciliationTests(unittest.TestCase):
    def test_preview(self):
        sale = dict(id="s", sale_id="s", currency="EUR", kind="sale", amount_minor=1000, evidence="source:s")
        fee = dict(sale, id="f", kind="fee", amount_minor=100)
        refund = dict(sale, id="r", kind="refund", amount_minor=200)
        usd = dict(sale, id="u", sale_id="u", currency="USD")
        result = preview([sale, sale, fee, refund, usd])
        self.assertEqual(result["currencies"]["EUR"]["net"], 700)
        self.assertEqual(result["currencies"]["USD"]["net"], 1000)
        self.assertFalse(result["booked"])
        self.assertEqual(len(result["evidence_hashes"]), 4)
    def test_conflict(self):
        sale = dict(id="s", sale_id="s", currency="EUR", kind="sale", amount_minor=1000, evidence="source:s")
        result = preview([sale, dict(sale, amount_minor=2000)])
        self.assertEqual(result["conflicting_ids"], ["s"])
        self.assertEqual(result["currencies"], {})
    def test_invalid(self):
        with self.assertRaises(ValueError):
            preview([{}])
