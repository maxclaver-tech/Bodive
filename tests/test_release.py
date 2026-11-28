import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile
from openpyxl import load_workbook
from bodive import director, validation, release
from bodive.memory import Memory, Refused

class ReleaseTests(unittest.TestCase):
    def test_localization_and_receipts(self):
        with tempfile.TemporaryDirectory() as d:
            m=Memory("simulation",Path(d)/"db.sqlite")
            ident=director.plan(m,"Personal budget spreadsheet",1200,400,0,None)
            prop=m.propose_validation(validation.build(m,ident))
            m.decide_validation(prop,m.validation(prop)["digest"],True,"test")
            with ZipFile(BytesIO(release.package(m,prop,"es"))) as z:
                self.assertEqual(len(z.namelist()),6)
                wb=load_workbook(BytesIO(z.read("budget-review.xlsx")))
                self.assertEqual(wb["Plan"]["A4"].value,"Salario")
                self.assertEqual(wb["Dashboard"]["G4"].value,"=Actual!B20-Plan!B20")
                self.assertTrue(z.read("cover-review.png").startswith(b"\x89PNG"))
            m.record_product_receipt(ident,1200,200,"receipt-1","test")
            with self.assertRaises(Refused):
                m.record_product_receipt(ident,1200,200,"receipt-1","test")
            self.assertEqual(m.product_receipts(ident)["net"],1000)
            self.assertEqual(m.report()["income_cents"],1000)
            self.assertEqual(m.report()["committed_cents"],0)
