import tempfile
import unittest
from pathlib import Path
from bodive import director, validation
from bodive.memory import Memory, Refused, MANUAL_KINDS

class ValidationTests(unittest.TestCase):
    def test_acceptance_never_authorizes_payment(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            dossier=director.plan(m,"Budget spreadsheet",1200,400,0,None)
            plan=validation.build(m,dossier)
            identifier=m.propose_validation(plan)
            row=m.validation(identifier)
            self.assertEqual(row["status"],"pending")
            self.assertEqual(plan["maximum_new_spend_cents"],0)
            with self.assertRaises(Refused):
                m.decide_validation(identifier,"wrong",True,"test")
            m.decide_validation(identifier,row["digest"],True,"test")
            self.assertEqual(m.validation(identifier)["status"],"accepted")
            with self.assertRaises(Refused):
                m.decide_validation(identifier,row["digest"],True,"test")
            with self.assertRaises(Refused):
                m.claim(identifier,MANUAL_KINDS|{"claude"})
            self.assertEqual(m.report()["committed_cents"],0)
            identifier=m.propose_validation(plan)
            m.stop("test")
            with self.assertRaises(Refused):
                m.decide_validation(identifier,m.validation(identifier)["digest"],True,"test")

    def test_negative_margin_refused(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            dossier=director.plan(m,"Budget spreadsheet",100,400,0,None)
            with self.assertRaises(Refused):
                validation.build(m,dossier)
