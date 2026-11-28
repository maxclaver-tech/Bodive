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


    def test_provider_preview(self):
        from unittest.mock import Mock, patch
        from bodive.store import Store
        sale = dict(id="abc", currency="eur", price=1200, test=False,
                    refunded=False, disputed=False, chargebacked=False,
                    email="private@example.invalid")
        http = Mock()
        http.request.return_value = {"success": True, "sales": [
            sale, sale, dict(sale, id="refund", refunded=True),
            dict(sale, id="unknown", test=None)], "next_page_key": "more"}
        with patch.dict("os.environ", {"GUMROAD_ACCESS_TOKEN": "fake-token"}):
            result = Store(http).reconciliation()
        self.assertEqual(result["currencies"]["EUR"]["sale"], 1200)
        self.assertIsNone(result["currencies"]["EUR"]["net"])
        self.assertIsNone(result["currencies"]["EUR"]["fee"])
        self.assertEqual(result["omitted"], 2)
        self.assertTrue(result["limited"])
        self.assertFalse(result["booked"])
        self.assertNotIn("private@", str(result))
        self.assertEqual(http.request.call_count, 1)
