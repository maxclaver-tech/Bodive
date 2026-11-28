import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bodive import daily
from bodive.memory import Memory


class DailyTests(unittest.TestCase):
    def test_persistent_opt_in_and_stop(self):
        with tempfile.TemporaryDirectory() as d:
            location=Path(d)/"db.sqlite"
            m=Memory("simulation",location)
            self.assertFalse(m.claim_daily_discovery())
            m.daily_setting(True)
            self.assertTrue(m.claim_daily_discovery())
            self.assertFalse(Memory("simulation",location).claim_daily_discovery())
            m.stop("test")
            self.assertFalse(m.daily_status()["enabled"])
            m.resume()
            self.assertFalse(m.claim_daily_discovery())

    def test_only_new_links(self):
        row={"topic":"x","status":"sampled","signals":[{"url":"a"},{"url":"b"}]}
        old={"candidates":[{**row,"signals":[{"url":"a"}]}]}
        new={"candidates":[row]}
        self.assertEqual(daily.changes(old,new)[0][2],[{"url":"b"}])
        self.assertEqual(daily.changes(new,new),[])

    def test_delivery_attempt_not_repeated(self):
        m=Mock(mode="live")
        m.claim_daily_discovery.side_effect=[True,False]
        m.get_discovery.return_value=None
        m.record_discovery.return_value="a"*32
        t=Mock()
        t.send.side_effect=RuntimeError("uncertain")
        with patch("bodive.discovery.discover",return_value={"candidates":[],"collected_at":"UTC"}):
            with self.assertRaises(RuntimeError):
                daily.run(m,t)
            self.assertFalse(daily.run(m,t))
        t.send.assert_called_once()
        m.daily_outcome.assert_called_once_with("failed_or_delivery_uncertain","a"*32)
