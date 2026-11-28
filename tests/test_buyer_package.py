import unittest
from unittest.mock import patch, Mock
from io import BytesIO
from zipfile import ZipFile
from openpyxl import load_workbook
from bodive import buyer_package, budget_product

class BuyerPackage(unittest.TestCase):
    def test_candidate(self):
        memory = Mock()
        with patch("bodive.budget_product.from_validation", return_value=budget_product.create()):
            data = buyer_package.build(memory, "test")
        with ZipFile(BytesIO(data)) as z:
            self.assertEqual(set(z.namelist()), {"personal-budget-en.xlsx","personal-budget-es.xlsx","README.txt"})
            for lang in ("en","es"):
                raw = z.read(f"personal-budget-{lang}.xlsx")
                budget_product.verify(raw)
                wb = load_workbook(BytesIO(raw))
                self.assertNotIn("prototype", wb["Start here"]["A1"].value.lower())
                self.assertNotIn("prototipo", wb["Start here"]["B13"].value.lower())
                self.assertNotIn("prototype", wb["Start here"]["B13"].value.lower())
                self.assertIn("Excel", wb["Start here"]["B12"].value)
                self.assertIsNone(wb["Actual"]["B4"].value)
        memory.check_running.assert_called()
