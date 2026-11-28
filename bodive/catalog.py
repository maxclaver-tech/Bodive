"""Original local review templates, not approved for sale."""
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from .memory import Refused

PRODUCTS = {"project_tracker": ("Task", "Owner", "Due date", "Status"),
            "habit_tracker": ("Habit", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")}
def generate(memory, product):
    memory.check_running()
    if product not in PRODUCTS:
        raise Refused("Unknown catalog product")
    wb = Workbook()
    ws = wb.active
    ws.title = "Tracker"
    ws.append(PRODUCTS[product])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="17354D")
        ws.column_dimensions[cell.column_letter].width = 22
    ws.freeze_panes = "B2"
    guide = wb.create_sheet("Review")
    guide.append(["Private review only; not approved for sale."])
    guide.append(["Original local layout; no third-party assets. Human rights and quality review required."])
    out = BytesIO()
    wb.save(out)
    data = out.getvalue()
    check = load_workbook(BytesIO(data))
    if tuple(c.value for c in check["Tracker"][1]) != PRODUCTS[product] or check._external_links:
        raise Refused("Catalog quality check failed")
    memory.check_running()
    return data
