import unittest
from io import BytesIO
from openpyxl import load_workbook
from bodive.budget_product import create, verify
from bodive.memory import Refused

class ProductQualityTests(unittest.TestCase):
    def test_valid(self):
        verify(create())

    def test_corruption(self):
        for sheet, cell, value in [
            ("Plan", "N4", "=0"),
            ("Actual", "B4", 100),
            ("Dashboard", "F4", "=0"),
            ("Dashboard", "B16", "=0"),
        ]:
            with self.subTest(sheet=sheet, cell=cell):
                wb = load_workbook(BytesIO(create()))
                wb[sheet][cell] = value
                out = BytesIO()
                wb.save(out)
                with self.assertRaises(Refused):
                    verify(out.getvalue())
