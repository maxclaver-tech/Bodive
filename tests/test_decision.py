import tempfile
import unittest
from pathlib import Path
from datetime import timedelta
from bodive import decision, director
from bodive.memory import Memory, now


class DecisionTests(unittest.TestCase):
    def test_scenario_and_catalog_without_mutation(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            identifier=director.plan(m,"Budget spreadsheet",1200,400,0,None)
            m.record_competition(identifier,{"source":"books","query":"budget",
                "collected_at":now().isoformat(),"observations":[{"title":"Guide","price_cents":549,
                "url":"https://books.apple.com/es/book/id123"}]})
            before=m.load(identifier)
            data=decision.analyze(m,identifier,549,400,500)
            self.assertEqual(data["assessment"]["margin"],149)
            self.assertEqual(data["stress_break_even"],4)
            self.assertEqual(data["catalogs"]["books"]["median"],549)
            self.assertIsNone(data["catalogs"]["etsy"])
            self.assertIn("SOLO VALIDACIÓN",data["verdict"])
            self.assertEqual(m.load(identifier),before)
            self.assertEqual(m.report()["committed_cents"],0)
            self.assertIn("referencia indirecta",decision.report(data))
            self.assertIn("NO INVERTIR",decision.analyze(m,identifier,100,400,0)["verdict"])

    def test_stale_data(self):
        self.assertFalse(decision.fresh({"collected_at":(now()-timedelta(days=31)).isoformat()}))
        self.assertFalse(decision.fresh(None))
