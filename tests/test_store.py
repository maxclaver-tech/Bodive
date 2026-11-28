import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bodive.store import Store
from bodive.memory import Memory, Refused

class StoreTests(unittest.TestCase):
    def test_read_only_and_minimal_data(self):
        h=Mock()
        with patch.dict("os.environ",{"GUMROAD_ACCESS_TOKEN":"fake-token"}):
            s=Store(h)
        h.request.return_value={"success":True,"products":[{"id":"abc==","name":"Budget","published":False,"email":"private@example.invalid"}]}
        self.assertEqual(s.products()["rows"],[{"id":"abc==","name":"Budget","published":False}])
        self.assertEqual(h.request.call_args.args[1],"https://api.gumroad.com/v2/products")
        self.assertNotIn("fake-token",h.request.call_args.args[1])
        self.assertNotIn("body",h.request.call_args.kwargs)
        with self.assertRaises(Refused):
            s.get("refund")
        h.request.return_value={"success":True,"sales":[{"id":"one","price":1200,"currency":"usd","email":"private@example.invalid"},
            {"id":"two","refunded":True},{"id":"three","test":True},{"id":"one"}],"next_page_url":"https://untrusted.invalid"}
        data=s.sales()
        self.assertEqual(data["counts"],{"other":1,"refund_or_dispute":1,"test":1})
        self.assertEqual(data["skipped"],1)
        self.assertTrue(data["limited"])
        self.assertNotIn("private@",str(data))
        self.assertEqual(h.request.call_count,2)

    def test_quota_and_stop(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            for _ in range(12):
                m.store_query_slot()
            with self.assertRaises(Refused):
                m.store_query_slot()
            self.assertEqual(m.report()["committed_cents"],0)
            m.stop("test")
            with self.assertRaises(Refused):
                m.store_query_slot()
