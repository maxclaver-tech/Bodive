import tempfile
import unittest
from pathlib import Path
from bodive import director, market
from bodive.memory import Memory, Refused


class MarketTests(unittest.TestCase):
    def test_scenarios_and_no_false_validation(self):
        with tempfile.TemporaryDirectory() as d:
            m = Memory("simulation",Path(d)/"db.sqlite")
            identifier = director.plan(m,"onboarding",1200,400,1600,None)
            for _ in range(2):
                m.market_observation(identifier,"purchase","https://example.com/product","Reported sale","telegram:42")
            result = market.assessment(m.load(identifier),m.market_observations(identifier),500)
            self.assertEqual(result["counts"]["purchase"],1)
            self.assertEqual(result["break_even"],2)
            self.assertEqual(result["scenarios"][10],6400)
            self.assertIn("no verificada",result["verdict"])
            self.assertEqual(m.report()["committed_cents"],0)

    def test_reject_sensitive_urls(self):
        for url in ("http://example.com","https://user:pass@example.com","https://example.com/?token=x"):
            with self.assertRaises(Refused):
                market.observation("interest",url,"note")

    def test_negative_margin(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            identifier=director.plan(m,"onboarding",100,200,0,None)
            result=market.assessment(m.load(identifier),[])
            self.assertIsNone(result["break_even"])
            self.assertIn("NO INVERTIR",result["verdict"])
