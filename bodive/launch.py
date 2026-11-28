"""Private launch preparation. Never uploads, publishes or contacts customers."""
from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED
from hashlib import sha256
from . import budget_product
from .memory import Refused

def prepare(memory, proposal_id):
    xlsx=budget_product.from_validation(memory,proposal_id)
    plan=memory.validation(proposal_id)["payload"]
    price=plan["price_cents"]
    # Fixed trusted copy; no third-party text or unverified testimonials.
    listing=(
        "# Personal Budget Spreadsheet\n\n"
        "Plan a year of income and expenses, record actual amounts, and compare your results.\n\n"
        "Includes a start guide, monthly plan, actual spending tracker and annual dashboard. "
        "Blue cells are editable inputs. Formulas calculate totals, net cash and savings rate.\n\n"
        "Format: XLSX, English, EUR. Requires Excel or compatible software with automatic calculation. "
        "No macros or online connection. Not financial advice.\n\n"
        f"Proposed price: {price/100:.2f} EUR (verify fees and tax before launch).\n"
        "DRAFT ONLY — verify workbook calculations and buyer interest before publication.\n")
    checklist=(
        "# Release checklist — private\n\n"
        "- [ ] Open the workbook in Excel; enter 2000 income and 1500 expenses; verify 500 net cash and 25% savings rate.\n"
        "- [ ] Verify zero income, negative net cash, annual totals and chart; reset all sample inputs.\n"
        "- [ ] Check the actual file against the description and original content rights.\n"
        "- [ ] Compare equivalent products and record real buyer feedback.\n"
        "- [ ] Verify Gumroad account, seller eligibility, fees, tax and refund terms.\n"
        "- [ ] Obtain separate publication authorization for the exact final product and price.\n"
        "- [ ] Upload only the reviewed buyer workbook, never this private package.\n"
        "- [ ] After publication, record the URL and verified net receipts; do not infer sales from clicks.\n")
    marketing=(
        "# Draft organic marketing — not approved for posting\n\n"
        "Do you know how much cash remains after your monthly expenses? "
        "Try writing down your income and spending categories, then subtract your expenses. "
        "A monthly plan and actual tracker can help you see the difference.\n\n"
        "Our Personal Budget Spreadsheet brings those steps into one Excel workbook. "
        "If you want to test the format, ask for a private preview.\n\n"
        "Use only an owned or opt-in channel. No unsolicited messages, paid ads or invented reviews. "
        "Add a product link only after publication is separately approved.\n")
    files={"personal-budget-review.xlsx":xlsx,"listing-draft.md":listing.encode(),
           "release-checklist.md":checklist.encode(),"marketing-draft.md":marketing.encode()}
    manifest="\n".join(f"{sha256(data).hexdigest()}  {name}" for name,data in files.items())+"\n"
    files["SHA256SUMS.txt"]=manifest.encode()
    out=BytesIO()
    with ZipFile(out,"w",compression=ZIP_DEFLATED) as z:
        for name,data in files.items():
            z.writestr(name,data)
    result=out.getvalue()
    if len(result)>5_000_000:
        raise Refused("Paquete demasiado grande")
    memory.check_running()
    return result

def record_feedback(memory,proposal_id,participants,interested,note,actor):
    if not 1<=participants<=100 or not 0<=interested<=participants or not 1<=len(note.strip())<=300:
        raise Refused("Datos de validación no válidos")
    memory.record_validation_feedback(proposal_id,participants,interested,note.strip(),actor)
