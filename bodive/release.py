"""Localized review packages; no external publishing or financial authorization."""
from io import BytesIO
from hashlib import sha256
from zipfile import ZipFile, ZIP_DEFLATED
from openpyxl import load_workbook
from PIL import Image, ImageDraw, ImageFont
from . import budget_product
from .memory import Refused

SPANISH={
"PERSONAL BUDGET | Review prototype":"PRESUPUESTO PERSONAL | Prototipo de revisión",
"Purpose":"Objetivo","Currency":"Moneda","1. Plan":"1. Planificar","2. Actual":"2. Registrar",
"3. Review":"3. Revisar","4. Savings":"4. Ahorro","5. Variance":"5. Diferencia",
"Example":"Ejemplo","Privacy":"Privacidad","Compatibility":"Compatibilidad","Status":"Estado",
"Plan and track income, expenses and savings for one calendar year.":"Planifica y registra ingresos, gastos y ahorro durante un año.",
"EUR. Enter non-negative amounts. All months start blank.":"EUR. Introduce importes no negativos. Todos los meses empiezan vacíos.",
"Enter expected income and expenses in the blue cells of Plan.":"Introduce los ingresos y gastos previstos en las celdas azules de Plan.",
"Enter actual monthly amounts in the blue cells of Actual.":"Introduce los importes reales mensuales en las celdas azules de Actual.",
"Dashboard compares income, spending and remaining cash.":"Dashboard compara ingresos, gastos y saldo neto del periodo.",
"Net cash = income minus expenses; it is not an account balance.":"Saldo neto = ingresos menos gastos; no representa el saldo bancario.",
"Actual net minus planned net. Positive means above plan.":"Saldo real menos saldo previsto. Un valor positivo supera el plan.",
"Income 2,000; expenses 1,500; net cash 500; savings rate 25%.":"Ingresos 2.000; gastos 1.500; saldo 500; tasa de ahorro 25%.",
"Keep this file private; no macros, external links or online connection.":"Mantén el archivo privado. Sin macros, enlaces externos ni conexión en línea.",
"Open in Excel or a compatible spreadsheet app with automatic calculation.":"Abre en Excel o una aplicación compatible con cálculo automático.",
"Review prototype, not yet approved for sale. Not financial advice.":"Prototipo de revisión, no autorizado para la venta. No es asesoramiento financiero.",
"Plan | Monthly amounts":"Previsión | Importes mensuales","Actual | Monthly amounts":"Real | Importes mensuales",
"Category":"Categoría","Annual total":"Total anual","Salary":"Salario","Freelance":"Autónomo","Other income":"Otros ingresos",
"Housing":"Vivienda","Utilities":"Suministros","Groceries":"Alimentación","Transport":"Transporte","Insurance":"Seguros",
"Health":"Salud","Debt payments":"Deudas","Leisure":"Ocio","Other expenses":"Otros gastos","Total income":"Ingresos totales",
"Total expenses":"Gastos totales","Net cash":"Saldo neto","Savings rate":"Tasa de ahorro",
"YEAR OVERVIEW | Plan vs actual":"RESUMEN ANUAL | Previsión y real","Month":"Mes","Plan income":"Ingresos previstos",
"Actual income":"Ingresos reales","Plan expenses":"Gastos previstos","Actual expenses":"Gastos reales",
"Actual net":"Saldo real","Net variance":"Diferencia neta",
**dict(zip(budget_product.MONTHS,("Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic")))}
def workbook(data, language):
    if language not in {"en","es"}:
        raise Refused("Idioma no disponible")
    budget_product.verify(data)
    if language=="en":
        return data
    wb=load_workbook(BytesIO(data))
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value,str) and c.data_type!="f" and c.value in SPANISH:
                    c.value=SPANISH[c.value]
        for dv in ws.data_validations.dataValidation:
            dv.errorTitle="Importe no válido"
            dv.error="Introduce un número no negativo."
    # Keep internal sheet identifiers unchanged to preserve formula references.
    wb["Dashboard"]._charts[0].title="Saldo neto mensual real"
    for ws in wb:
        for row in ws.iter_rows():
            for c in row:
                if c.data_type == "s" and c.value in SPANISH and SPANISH[c.value] != c.value:
                    raise Refused("Incomplete localization")
    out=BytesIO()
    wb.save(out)
    result=out.getvalue()
    budget_product.verify(result)
    return result

def cover(language):
    if language not in {"en", "es"}:
        raise Refused("Idioma no disponible")
    # Local Pillow rendering; no network, external assets or fonts downloaded.
    im=Image.new("RGB",(1200,675),"#17354d")
    d=ImageDraw.Draw(im)
    d.rectangle((0,0,1200,16),fill="#34b8b2")
    font=lambda size:ImageFont.load_default(size=size)
    title="PRESUPUESTO PERSONAL" if language=="es" else "PERSONAL BUDGET"
    sub="Planifica, registra y compara" if language=="es" else "Plan, track and compare"
    title_font=font(54)
    while d.textbbox((0,0),title,font=title_font)[2]>1060:
        title_font=font(title_font.size-2)
    d.text((70,88),title,font=title_font,fill="white")
    d.text((73,170),sub,font=font(32),fill="#c9e6e5")
    labels=("INGRESOS","GASTOS","SALDO") if language=="es" else ("INCOME","EXPENSES","NET CASH")
    for i,label in enumerate(labels):
        x=72+i*360
        d.rounded_rectangle((x,280,x+330,460),radius=18,fill="#f1f7f7")
        d.text((x+25,305),label,font=font(27),fill="#17354d")
        d.rectangle((x+25,380,x+280-i*45,401),fill="#237c80")
    d.text((74,550),"XLSX  |  EUR  |  12 MONTHS" if language=="en" else "XLSX  |  EUR  |  12 MESES",font=font(28),fill="white")
    d.text((74,606),"BODIVE - REVIEW" if language=="en" else "BODIVE - REVISION",font=font(20),fill="#c9e6e5")
    out=BytesIO();im.save(out,format="PNG");return out.getvalue()

def package(memory,identifier,language):
    data=workbook(budget_product.from_validation(memory,identifier),language)
    plan=memory.validation(identifier)["payload"]
    price=plan["price_cents"]/100
    if language=="es":
        listing=f"# Presupuesto personal\n\nPlantilla Excel para planificar ingresos y gastos, registrar importes reales y comparar el saldo mensual y anual.\n\nXLSX en español (nombres internos de hojas en inglés), EUR, sin macros. Precio propuesto: {price:.2f} EUR. Borrador privado; revisar cálculo, demanda y costes antes de publicar."
        marketing="Registra tus ingresos y gastos mensuales y compara el resultado con tu previsión. Solicita una muestra privada si quieres probar el formato. Borrador; no publicar sin autorización."
    else:
        listing=f"# Personal Budget Spreadsheet\n\nPlan income and expenses, record actual amounts, compare monthly and annual cash flow.\n\nEnglish XLSX, EUR, no macros. Proposed price: {price:.2f} EUR. Private draft; verify calculation, demand and costs before publishing."
        marketing="Track income and expenses and compare the result with your plan. Ask for a private preview if you want to test the format. Draft; do not post without approval."
    checklist="PRIVATE REVIEW / REVISION PRIVADA\nTest Excel recalculation: 2000 income, 1500 expenses, 500 net, 25% savings. Test zero income, negative net and annual totals. Verify buyer feedback, fees and rights. Separate approval required before publication. Do not upload this ZIP."
    files={"budget-review.xlsx":data,"cover-review.png":cover(language),"listing-draft.md":listing.encode(),
           "marketing-draft.md":marketing.encode(),"release-checklist.txt":checklist.encode()}
    quality = ("PRIVATE QUALITY REVIEW / REVISION PRIVADA\n"
               "Structural formulas and input controls checked.\n"
               "Spreadsheet recalculation and visual inspection in Excel still required.\n"
               "No publication approval, verified demand or sales claim.\n")
    files["quality-review.txt"] = quality.encode()
    files["SHA256SUMS.txt"]="".join(f"{sha256(v).hexdigest()}  {k}\n" for k,v in files.items()).encode()
    out=BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED) as z:
        for name,content in files.items():
            z.writestr(name,content)
    result=out.getvalue()
    if len(result)>5_000_000:
        raise Refused("Paquete demasiado grande")
    memory.check_running()
    return result
