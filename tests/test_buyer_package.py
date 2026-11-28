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
                if lang == "en":
                    budget_product.verify(raw)
                wb = load_workbook(BytesIO(raw))
                guide = wb["Inicio" if lang == "es" else "Start here"]
                actual = wb["Registro real" if lang == "es" else "Actual"]
                if lang == "es":
                    self.assertEqual(wb.sheetnames, list(buyer_package.SHEET_NAMES.values()))
                    self.assertEqual(wb["Resumen"]["B4"].value, "='Presupuesto'!B7")
                    self.assertEqual(wb["Resumen"]["G4"].value, "='Registro real'!B20-'Presupuesto'!B20")
                    self.assertIn("Resumen", wb["Resumen"]._charts[0].series[0].val.numRef.f)
                    self.assertIn("Categorías", wb["Categorías"]._charts[0].series[0].val.numRef.f)
                    self.assertIn("Sigue Inicio", z.read("README.txt").decode())
                self.assertNotIn("prototype", guide["A1"].value.lower())
                self.assertNotIn("prototipo", guide["B13"].value.lower())
                self.assertNotIn("prototype", guide["B13"].value.lower())
                self.assertIn("Excel", guide["B12"].value)
                self.assertIsNone(actual["B4"].value)
        memory.check_running.assert_called()
