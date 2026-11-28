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
                self.assertEqual(set(z.namelist()), {
                    "budget-review.xlsx", "cover-review.png", "listing-draft.md",
                    "marketing-draft.md", "release-checklist.txt", "quality-review.txt",
                    "SHA256SUMS.txt",
                })
                self.assertIn(b"recalculation", z.read("quality-review.txt"))
                from hashlib import sha256
                expected = "".join(f"{sha256(z.read(name)).hexdigest()}  {name}\n"
                                   for name in z.namelist() if name != "SHA256SUMS.txt")
                self.assertEqual(z.read("SHA256SUMS.txt").decode(), expected)
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
