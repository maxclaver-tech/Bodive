"""Buyer-facing candidate only; never publishes or authorizes publication."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import load_workbook
from . import budget_product, release
from .memory import Refused

def build(memory, identifier):
    source = budget_product.from_validation(memory, identifier)
    files = {}
    for lang in ("en", "es"):
        wb = load_workbook(BytesIO(release.workbook(source, lang)))
        guide = wb["Start here"]
        guide["A1"] = "PERSONAL BUDGET" if lang == "en" else "PRESUPUESTO PERSONAL"
        guide["B12"] = "For personal budgeting only. Not financial advice." if lang == "en" else "Para presupuesto personal. No es asesoramiento financiero."
        out = BytesIO()
        wb.save(out)
        data = out.getvalue()
        budget_product.verify(data)
        files[f"personal-budget-{lang}.xlsx"] = data
    files["README.txt"] = ("EN: Open personal-budget-en.xlsx in Excel with automatic calculation. Follow Start here. Enter amounts in EUR in blue cells. Example figures are fictional.\n"
                           "ES: Abre personal-budget-es.xlsx en Excel con cálculo automático. Sigue Start here. Introduce importes en EUR en celdas azules. Las cifras del ejemplo son ficticias.\n").encode()
    out = BytesIO()
    with ZipFile(out, "w", ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)
    data = out.getvalue()
    if len(data) > 5000000:
        raise Refused("Package too large")
    memory.check_running()
    return data
