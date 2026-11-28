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


    def test_localized_outputs(self):
        from bodive.release import workbook, cover
        from PIL import Image
        for language in ("en", "es"):
            data = workbook(create(), language)
            verify(data)
            wb = load_workbook(BytesIO(data))
            self.assertEqual(wb["Plan"]["A4"].value, "Salario" if language == "es" else "Salary")
            with Image.open(BytesIO(cover(language))) as im:
                self.assertEqual(im.size, (1200, 675))
                self.assertEqual(im.format, "PNG")
        with self.assertRaises(Refused):
            cover("xx")
