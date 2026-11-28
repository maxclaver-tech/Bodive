import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from openpyxl import load_workbook
from bodive import director, validation, budget_product
from bodive.memory import Memory, Refused

class BudgetProductTests(unittest.TestCase):
    def test_requires_accepted_plan_and_returns_workbook(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            dossier=director.plan(m,"Personal budget spreadsheet",1200,400,0,None)
            p=m.propose_validation(validation.build(m,dossier))
            with self.assertRaises(Refused):
                budget_product.from_validation(m,p)
            m.decide_validation(p,m.validation(p)["digest"],True,"test")
            data=budget_product.from_validation(m,p)
            wb=load_workbook(BytesIO(data))
            self.assertEqual(wb["Actual"]["B20"].value,"=B7-B18")
            self.assertIsNone(wb["Actual"]["B4"].value)
            self.assertEqual(wb["Dashboard"]["G4"].value,"=Actual!B20-Plan!B20")
            self.assertEqual(m.report()["committed_cents"],0)
            m.stop("test")
            with self.assertRaises(Refused):
                budget_product.from_validation(m,p)
