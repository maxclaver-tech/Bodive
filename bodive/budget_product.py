"""Original, deterministic spreadsheet prototype for a personal budget."""
from io import BytesIO
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart import BarChart, Reference
from .memory import Refused

MONTHS=("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")
INCOME=("Salary","Freelance","Other income")
EXPENSE=("Housing","Utilities","Groceries","Transport","Insurance","Health","Debt payments","Leisure","Other expenses")
MONEY='#,##0.00 "€";[Red](#,##0.00) "€";–'
TOPIC="personal budget spreadsheet"

def heading(ws, title, columns):
    ws.merge_cells(start_row=1,start_column=1,end_row=1,end_column=columns)
    cell=ws.cell(1,1,title)
    cell.font=Font(name="Calibri",size=19,bold=True,color="FFFFFF")
    cell.fill=PatternFill("solid",fgColor="17354D")
    ws.row_dimensions[1].height=32
    ws.sheet_view.showGridLines=False

def header(ws,row,labels):
    for i,label in enumerate(labels,1):
        cell=ws.cell(row,i,label)
        cell.fill=PatternFill("solid",fgColor="237C80")
        cell.font=Font(bold=True,color="FFFFFF")
        cell.alignment=Alignment(wrap_text=True,vertical="center")
    ws.row_dimensions[row].height=30

def create():
    wb=Workbook()
    guide=wb.active
    guide.title="Start here"
    heading(guide,"PERSONAL BUDGET | Review prototype",2)
    guide.column_dimensions["A"].width=24
    guide.column_dimensions["B"].width=84
    instructions=[
        ("Purpose","Plan and track income, expenses and savings for one calendar year."),
        ("Currency","EUR. Enter non-negative amounts. All months start blank."),
        ("1. Plan","Enter expected income and expenses in the blue cells of Plan."),
        ("2. Actual","Enter actual monthly amounts in the blue cells of Actual."),
        ("3. Review","Dashboard compares income, spending and remaining cash."),
        ("4. Savings","Net cash = income minus expenses; it is not an account balance."),
        ("5. Variance","Actual net minus planned net. Positive means above plan."),
        ("Example","Income 2,000; expenses 1,500; net cash 500; savings rate 25%."),
        ("Privacy","Keep this file private; no macros, external links or online connection."),
        ("Compatibility","Open in Excel or a compatible spreadsheet app with automatic calculation."),
        ("Status","Review prototype, not yet approved for sale. Not financial advice.")]
    for i,(label,note) in enumerate(instructions,3):
        guide.cell(i,1,label).font=Font(bold=True,color="17354D")
        c=guide.cell(i,2,note)
        c.alignment=Alignment(wrap_text=True,vertical="center")
        guide.row_dimensions[i].height=32
    for name in ("Plan","Actual"):
        ws=wb.create_sheet(name)
        heading(ws,name+" | Monthly amounts",14)
        header(ws,3,("Category",*MONTHS,"Annual total"))
        ws.column_dimensions["A"].width=25
        for col in "BCDEFGHIJKLMN":
            ws.column_dimensions[col].width=14
        ws.freeze_panes="B4"
        for row,label in [(4+x,v) for x,v in enumerate(INCOME)]+[(9+x,v) for x,v in enumerate(EXPENSE)]:
            ws.cell(row,1,label)
            for col in range(2,14):
                c=ws.cell(row,col)
                c.fill=PatternFill("solid",fgColor="E8F3FF")
                c.font=Font(color="1755A0")
                c.number_format=MONEY
            ws.cell(row,14,f"=SUM(B{row}:M{row})").number_format=MONEY
        dv=DataValidation(type="decimal",operator="between",formula1=0,formula2=100000000,
                          allow_blank=True,showErrorMessage=True,errorStyle="stop",
                          errorTitle="Invalid amount",error="Enter a non-negative number.")
        ws.add_data_validation(dv)
        dv.add("B4:M6")
        dv.add("B9:M17")
        for r,label in ((7,"Total income"),(18,"Total expenses"),(20,"Net cash"),(21,"Savings rate")):
            ws.cell(r,1,label)
            for col in range(1,15):
                c=ws.cell(r,col)
                c.fill=PatternFill("solid",fgColor="DCEBEC")
                c.font=Font(bold=True,color="17354D")
            for col in range(2,15):
                letter=ws.cell(3,col).column_letter
                formula={7:f"=SUM({letter}4:{letter}6)",18:f"=SUM({letter}9:{letter}17)",
                         20:f"={letter}7-{letter}18",21:f'=IF({letter}7=0,"",{letter}20/{letter}7)'}[r]
                ws.cell(r,col,formula).number_format="0.0%" if r==21 else MONEY
    dash=wb.create_sheet("Dashboard",1)
    heading(dash,"YEAR OVERVIEW | Plan vs actual",7)
    header(dash,3,("Month","Plan income","Actual income","Plan expenses","Actual expenses","Actual net","Net variance"))
    dash.column_dimensions["A"].width=16
    for col in "BCDEFG":
        dash.column_dimensions[col].width=19
    for i,month in enumerate(MONTHS,4):
        letter="BCDEFGHIJKLM"[i-4]
        dash.cell(i,1,month)
        for col,formula in enumerate((f"=Plan!{letter}7",f"=Actual!{letter}7",f"=Plan!{letter}18",
                f"=Actual!{letter}18",f"=Actual!{letter}20",f"=Actual!{letter}20-Plan!{letter}20"),2):
            dash.cell(i,col,formula).number_format=MONEY
    dash.cell(16,1,"Annual total")
    for col in "BCDEFG":
        dash[f"{col}16"]=f"=SUM({col}4:{col}15)"
        dash[f"{col}16"].number_format=MONEY
    for c in dash[16][:7]:
        c.font=Font(bold=True,color="17354D")
        c.fill=PatternFill("solid",fgColor="DCEBEC")
    dash.freeze_panes="B4"
    chart=BarChart()
    chart.title="Monthly actual net cash"
    chart.y_axis.title="EUR"
    chart.add_data(Reference(dash,min_col=6,min_row=3,max_row=15),titles_from_data=True)
    chart.set_categories(Reference(dash,min_col=1,min_row=4,max_row=15))
    chart.width=23
    chart.height=10
    dash.add_chart(chart,"A19")
    out=BytesIO()
    wb.save(out)
    data=out.getvalue()
    verify(data)
    return data

def verify(data):
    wb=load_workbook(BytesIO(data),data_only=False)
    if wb.sheetnames!=["Start here","Dashboard","Plan","Actual"] or wb._external_links:
        raise Refused("Workbook structure failed")
    for name in ("Plan","Actual"):
        ws=wb[name]
        for col in "BCDEFGHIJKLMN":
            expected={7:f"=SUM({col}4:{col}6)",18:f"=SUM({col}9:{col}17)",
                      20:f"={col}7-{col}18",21:f'=IF({col}7=0,"",{col}20/{col}7)'}
            if any(ws[f"{col}{r}"].value!=v for r,v in expected.items()):
                raise Refused("Workbook formula check failed")
    if wb["Dashboard"]["G16"].value!="=SUM(G4:G15)":
        raise Refused("Dashboard formula check failed")

def from_validation(memory,identifier):
    memory.check_running()
    row=memory.validation(identifier)
    if row["status"]!="accepted":
        raise Refused("Se requiere un plan de validación aceptado")
    dossier=memory.load(row["payload"]["dossier_id"])
    if dossier["evidence"]["topic"].strip().casefold()!=TOPIC:
        raise Refused("Por ahora solo se admite Personal budget spreadsheet")
    data=create()
    memory.check_running()
    return data
