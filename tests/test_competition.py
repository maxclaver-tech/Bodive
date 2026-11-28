import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bodive import competition, director
from bodive.memory import Memory, Refused


class CompetitionTests(unittest.TestCase):
    def test_books_only_eur_and_fixed_links(self):
        h=Mock()
        row={"kind":"ebook","currency":"EUR","trackId":123,"trackName":"Budget guide",
             "price":4.99,"trackViewUrl":"http://localhost"}
        h.request.return_value={"results":[row,row,{**row,"trackId":124,"currency":"USD"},
            {**row,"trackId":125,"price":0},{**row,"trackId":126,"price":"NaN"}]}
        s=competition.catalog(h,"Personal budgeting","books")
        self.assertEqual(len(s["observations"]),2)
        self.assertEqual(s["observations"][0]["url"],"https://books.apple.com/es/book/id123")
        self.assertEqual(competition.summarize(s)["median"],499)

    def test_etsy_optional_and_only_digital_eur(self):
        h=Mock()
        with patch.dict("os.environ",{"BODIVE_ETSY_API_KEY":""}):
            with self.assertRaises(Refused):
                competition.catalog(h,"Budget spreadsheet","etsy")
        h.request.assert_not_called()
        row={"listing_type":"download","listing_id":123,"title":"Budget",
             "price":{"amount":550,"divisor":100,"currency_code":"EUR"}}
        h.request.return_value={"results":[row,{**row,"listing_id":124,"listing_type":"physical"}]}
        with patch.dict("os.environ",{"BODIVE_ETSY_API_KEY":"fake:fake"}):
            s=competition.catalog(h,"Budget spreadsheet","etsy")
        self.assertEqual(len(s["observations"]),1)
        self.assertEqual(s["observations"][0]["price_cents"],550)

    def test_storage_separate_from_demand(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            identifier=director.plan(m,"Budget spreadsheet",1200,400,0,None)
            s={"source":"books","observations":[]}
            m.record_competition(identifier,s)
            self.assertEqual(m.latest_competition(identifier,"books"),s)
            self.assertIsNone(m.latest_competition(identifier,"etsy"))
            self.assertEqual(m.market_observations(identifier),[])
            self.assertEqual(m.report()["committed_cents"],0)
