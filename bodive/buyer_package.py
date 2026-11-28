"""Buyer-facing candidate only; never publishes or authorizes publication."""
import re
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import load_workbook
from . import budget_product, release
from .memory import Refused

SHEET_NAMES = {"Start here": "Inicio", "Dashboard": "Resumen", "Plan": "Presupuesto", "Actual": "Registro real", "Goals": "Objetivos", "Categories": "Categorías", "Example": "Ejemplo"}

def translate_refs(value, names):
    for old, new in names.items():
        value = re.sub(r"(?<![\w'])" + re.escape(old) + r"!|'" + re.escape(old) + r"'!", lambda _: "'" + new + "'!", value)
    return value

def localize_tabs(wb):
    for ws in wb:
        for row in ws.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    cell.value = translate_refs(cell.value, SHEET_NAMES)
        for chart in ws._charts:
            for series in chart.series:
                for source in (series.val, series.cat, series.tx):
                    if source is not None:
                        for attr in ("numRef", "strRef", "multiLvlStrRef"):
                            ref = getattr(source, attr, None)
                            if ref is not None and ref.f:
                                ref.f = translate_refs(ref.f, SHEET_NAMES)
    for old, new in SHEET_NAMES.items():
        wb[old].title = new
    guide = wb["Inicio"]
    guide["B5"] = "Introduce los ingresos y gastos previstos en las celdas azules de Presupuesto."
    guide["B6"] = "Introduce los importes reales mensuales en las celdas azules de Registro real."
    guide["B7"] = "Resumen compara ingresos, gastos y saldo neto del periodo."

def build(memory, identifier):
    source = budget_product.from_validation(memory, identifier)
    files = {}
    for lang in ("en", "es"):
        wb = load_workbook(BytesIO(release.workbook(source, lang)))
        guide = wb["Start here"]
        guide["A1"] = "PERSONAL BUDGET" if lang == "en" else "PRESUPUESTO PERSONAL"
        guide["A13"] = "Disclaimer" if lang == "en" else "Aviso"
        guide["B13"] = "For personal budgeting only. Not financial advice." if lang == "en" else "Para presupuesto personal. No es asesoramiento financiero."
        if lang == "es":
            localize_tabs(wb)
        out = BytesIO()
        wb.save(out)
        data = out.getvalue()
        if lang == "en":
            budget_product.verify(data)
        else:
            check = load_workbook(BytesIO(data))
            if check.sheetnames != list(SHEET_NAMES.values()) or check._external_links:
                raise Refused("Localized workbook structure failed")
            reverse = {new: old for old, new in SHEET_NAMES.items()}
            for ws in check:
                for row in ws.iter_rows():
                    for cell in row:
                        if cell.data_type == "f":
                            value = translate_refs(cell.value, reverse)
                            for old in SHEET_NAMES:
                                value = value.replace("'" + old + "'!", old + "!")
                            cell.value = value
            for new, old in reverse.items():
                check[new].title = old
            verified = BytesIO()
            check.save(verified)
            budget_product.verify(verified.getvalue())
        files[f"personal-budget-{lang}.xlsx"] = data
    files["README.txt"] = ("EN: Open personal-budget-en.xlsx in Excel with automatic calculation. Follow Start here. Enter amounts in EUR in blue cells. Example figures are fictional.\n"
                           "ES: Abre personal-budget-es.xlsx en Excel con cálculo automático. Sigue Inicio. Introduce importes en EUR en celdas azules. Las cifras del ejemplo son ficticias.\n").encode()
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    data = out.getvalue()
    if len(data) > 5000000:
        raise Refused("Package too large")
    memory.check_running()
    return data
