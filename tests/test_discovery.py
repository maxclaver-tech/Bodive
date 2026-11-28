import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from bodive import discovery
from bodive.memory import Memory, Refused


class DiscoveryTests(unittest.TestCase):
    def test_bounded_discovery_and_storage(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            with patch("bodive.community.search",return_value={"observations":[{"comments":3}]} ) as search:
                data=discovery.discover(m,Mock())
                self.assertEqual(search.call_count,4)
            self.assertEqual(len(data["candidates"]),4)
            identifier=m.record_discovery(data)
            self.assertEqual(m.get_discovery(identifier)["snapshot"],data)
            self.assertEqual(discovery.candidate(data,1)["comment_count"],3)
            self.assertEqual(m.report()["committed_cents"],0)
            m.stop("test")
            with self.assertRaises(Refused):
                discovery.discover(m,Mock())

    def test_unavailable_is_not_zero_demand(self):
        m=Mock()
        with patch("bodive.community.search",side_effect=Refused("network")):
            data=discovery.discover(m,Mock())
        self.assertTrue(all(r["status"]=="unavailable" for r in data["candidates"]))
        with self.assertRaises(Refused):
            discovery.candidate(data,1)
