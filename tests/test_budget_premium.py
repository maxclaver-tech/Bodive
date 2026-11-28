import unittest
from io import BytesIO
from openpyxl import load_workbook
from bodive import budget_product, release

class PremiumBudget(unittest.TestCase):
    def test_features(self):
        for language in ("en","es"):
            data=release.workbook(budget_product.create(),language)
            wb=load_workbook(BytesIO(data))
            self.assertEqual(wb["Goals"]["A3"].value,"Objetivo" if language=="es" else "Goal")
            self.assertIsNone(wb["Goals"]["B4"].value)
            self.assertEqual(wb["Categories"]["C4"].value,"=Actual!N9")
            self.assertEqual(wb["Example"]["B4"].value,2000)
            self.assertEqual(wb["Dashboard"]["B37"].value,'=IF(C16=0,"",F16/C16)')
            self.assertEqual(len(wb["Categories"]._charts),1)
