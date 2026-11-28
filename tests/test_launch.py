import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from bodive import director, validation, launch
from bodive.memory import Memory, Refused

class LaunchTests(unittest.TestCase):
    def test_private_package_and_feedback(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            dossier=director.plan(m,"Personal budget spreadsheet",1200,400,0,None)
            p=m.propose_validation(validation.build(m,dossier))
            with self.assertRaises(Refused):
                launch.prepare(m,p)
            m.decide_validation(p,m.validation(p)["digest"],True,"test")
            with ZipFile(BytesIO(launch.prepare(m,p))) as z:
                self.assertEqual(len(z.namelist()),5)
                self.assertIn(b"12.00 EUR",z.read("listing-draft.md"))
                self.assertTrue(z.read("personal-budget-review.xlsx").startswith(b"PK"))
            self.assertEqual(m.portfolio()[0]["id"],dossier)
            launch.record_feedback(m,p,5,2,"Anonymous summary","test")
            self.assertEqual(m.validation_feedback(p)["interested"],2)
            with self.assertRaises(Refused):
                launch.record_feedback(m,p,5,6,"Invalid","test")
            self.assertEqual(m.report()["committed_cents"],0)
            m.stop("test")
            with self.assertRaises(Refused):
                launch.prepare(m,p)
