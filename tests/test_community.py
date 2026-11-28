import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from bodive import community, director
from bodive.memory import Memory, now, Refused


class CommunityTests(unittest.TestCase):
    def test_bounded_fixed_endpoint_and_untrusted_fields(self):
        http=Mock()
        hit={"objectID":"123","title":"Freelancer discussion","points":5,"num_comments":3,
             "created_at_i":int(now().timestamp()),"url":"http://localhost/private"}
        http.request.return_value={"hits":[hit,hit,{**hit,"objectID":"bad"}]}
        result=community.search(http,"Freelancer onboarding")
        self.assertEqual(len(result["observations"]),1)
        self.assertEqual(result["observations"][0]["url"],"https://news.ycombinator.com/item?id=123")
        self.assertTrue(http.request.call_args.args[1].startswith("https://hn.algolia.com/api/v1/search?"))
        http.request.assert_called_once()
        with self.assertRaises(Refused):
            community.search(http,"https://localhost")

    def test_snapshot_is_separate_from_commercial_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            identifier=director.plan(m,"onboarding",1200,400,0,None)
            self.assertIsNone(m.latest_community(identifier))
            m.record_community(identifier,{"observations":[]})
            self.assertEqual(m.latest_community(identifier),{"observations":[]})
            self.assertEqual(m.market_observations(identifier),[])
            self.assertEqual(m.report()["committed_cents"],0)
            m.stop("test")
            with self.assertRaises(Refused):
                m.record_community(identifier,{"observations":[]})
