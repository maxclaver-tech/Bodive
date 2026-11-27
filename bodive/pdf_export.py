"""Local, bounded PDF rendering. No external resources or AI calls."""
import io
import json
import re
from xml.sax.saxutils import escape

from .memory import Refused


def render(markdown, title):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak

    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > 400_000:
        raise Refused("Contenido PDF vacío o demasiado extenso")
    # Render model content as literal text, never as HTML or executable markup.
    def safe(value):
        return escape(value.replace("\x00", "").replace("\t", "    "))

    out = io.BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CoverTitle", fontName="Helvetica-Bold", fontSize=30,
                              leading=36, alignment=TA_CENTER, textColor=colors.HexColor("#15354A")))
    styles.add(ParagraphStyle(name="CoverSub", fontName="Helvetica", fontSize=13,
                              leading=19, alignment=TA_CENTER, textColor=colors.HexColor("#526777")))
    styles.add(ParagraphStyle(name="WorkbookBody", fontName="Helvetica", fontSize=10.5,
                              leading=15, spaceAfter=7, splitLongWords=True))
    for key in ("Heading1", "Heading2", "Heading3"):
        styles[key].textColor = colors.HexColor("#15354A")
        styles[key].spaceBefore = 12
        styles[key].spaceAfter = 8
    story = [Spacer(1, 64*mm), Paragraph(safe(title), styles["CoverTitle"]),
             Spacer(1, 10*mm), Paragraph("Practical workbook", styles["CoverSub"]),
             Spacer(1, 40*mm), Paragraph("BODIVE | Review copy", styles["CoverSub"]), PageBreak()]
    for line in markdown.splitlines():
        line = line.strip()
        if not line:
            story.append(Spacer(1, 3*mm))
            continue
        if re.fullmatch(r"[-*_]{3,}", line):
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            level = min(len(heading[1]), 3)
            story.append(Paragraph(safe(heading[2]), styles[f"Heading{level}"]))
        else:
            # Preserve text, including table columns and checklist markers.
            line = re.sub(r"^[-*]\s+", "• ", line)
            line = line.replace("☐", "[ ]").replace("☑", "[x]")
            story.append(Paragraph(safe(line), styles["WorkbookBody"]))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5DC"))
        canvas.line(22*mm, 18*mm, 188*mm, 18*mm)
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#526777"))
        canvas.drawString(22*mm, 12*mm, "BODIVE | Review copy")
        canvas.drawRightString(188*mm, 12*mm, str(doc.page))
        canvas.restoreState()

    doc = SimpleDocTemplate(out, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm,
                            topMargin=22*mm, bottomMargin=26*mm, title=title, author="BODIVE")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    data = out.getvalue()
    if len(data) > 5_000_000:
        raise Refused("PDF demasiado grande")
    return data


def from_approval(memory, identifier):
    row = memory.get(identifier)
    if row["blocked"] or row["status"] in {"cancelled", "rejected"}:
        raise Refused("La solicitud no está disponible para exportación")
    payload = json.loads(row["payload"])
    if row["kind"] == "claude":
        result = json.loads(row["result"] or "{}")
        if result.get("stop_reason") != "end_turn" or not result.get("draft"):
            raise Refused("No se exportan borradores incompletos")
        markdown = result["draft"]
        title = memory.load(payload["dossier_id"])["evidence"]["topic"].title()
        if "chapter" in payload:
            title += f" | Chapter {payload['chapter']}"
    elif row["kind"] == "publish":
        markdown = payload.get("product_markdown")
        title = memory.load(payload["dossier_id"])["evidence"]["topic"].title()
    else:
        raise Refused("La solicitud no contiene un documento")
    return render(markdown, title)
