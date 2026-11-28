"""Local workbook PDF rendering; only fixed, escaped formatting tags."""
import io
import json
import re
from xml.sax.saxutils import escape

from .memory import Refused


def inline(value):
    """Escape first; only introduce our own fixed bold and italic tags."""
    value = escape(value.replace("\x00", "").replace("\t", "    "))
    value = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", value)
    return value


def table_cells(line):
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def render(markdown, title):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle,
        KeepTogether, HRFlowable,
    )

    if not isinstance(markdown, str) or not markdown.strip() or len(markdown) > 400_000:
        raise Refused("Contenido PDF vacío o demasiado extenso")
    navy = colors.HexColor("#15354A")
    teal = colors.HexColor("#007C78")
    muted = colors.HexColor("#526777")
    pale = colors.HexColor("#EDF5F4")
    border = colors.HexColor("#CBD5DC")
    white = colors.white
    width = A4[0] - 44*mm - 12
    body = ParagraphStyle("Body", fontName="Helvetica", fontSize=10.5, leading=14.5,
                          textColor=navy, spaceAfter=5, splitLongWords=True)
    label = ParagraphStyle("Label", parent=body, fontName="Helvetica-Bold", fontSize=9,
                           leading=12, textColor=teal, spaceAfter=3)
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=13, firstLineIndent=-10)
    headings = {n: ParagraphStyle(f"H{n}", parent=body, fontName="Helvetica-Bold",
                   fontSize=size, leading=size+4, spaceBefore=10, spaceAfter=6,
                   keepWithNext=True, textColor=navy if n==1 else teal)
                for n,size in ((1,21),(2,15),(3,12))}
    cell = ParagraphStyle("Cell", parent=body, fontSize=9.5, leading=12.5, spaceAfter=0)
    header = ParagraphStyle("TableHeader", parent=cell, fontName="Helvetica-Bold", textColor=white)
    cover = ParagraphStyle("Cover", fontName="Helvetica-Bold", fontSize=31, leading=37,
                           textColor=white, spaceAfter=18)
    cover_sub = ParagraphStyle("CoverSub", fontName="Helvetica", fontSize=13, leading=19,
                               textColor=colors.HexColor("#CDE7E5"))
    story = [Spacer(1, 44*mm), Paragraph("BODIVE  /  WORKBOOK SERIES", cover_sub),
             Spacer(1, 13*mm), Paragraph(inline(title), cover),
             HRFlowable(width="32%", thickness=3, color=colors.HexColor("#5ED1C4"), hAlign="LEFT"),
             Spacer(1, 10*mm), Paragraph("Practical exercises &amp; reusable tools", cover_sub),
             Spacer(1, 30*mm), Paragraph("REVIEW EDITION", cover_sub), PageBreak()]
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if re.fullmatch(r"[-*_]{3,}", line):
            continue
        if line.startswith("|") and i < len(lines):
            sep = table_cells(lines[i])
            names = table_cells(line)
            if (2 <= len(names) <= 6 and len(sep)==len(names)
                    and all(re.fullmatch(r":?-{3,}:?", x) for x in sep)):
                rows = [names]
                i += 1
                while i < len(lines) and lines[i].strip().startswith("|"):
                    values = table_cells(lines[i])
                    if len(values) != len(names):
                        break
                    rows.append(values)
                    i += 1
                formatted = [[Paragraph(inline(v), header if r==0 else cell)
                              for v in values] for r,values in enumerate(rows)]
                widths = [width*.34,width*.66] if len(names)==2 else [width/len(names)]*len(names)
                t = Table(formatted, colWidths=widths, repeatRows=1, splitByRow=1, splitInRow=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND",(0,0),(-1,0),navy),
                    ("ROWBACKGROUNDS",(0,1),(-1,-1),[pale,white]),
                    ("VALIGN",(0,0),(-1,-1),"TOP"),
                    ("TOPPADDING",(0,0),(-1,-1),8),
                    ("BOTTOMPADDING",(0,0),(-1,-1),8),
                    ("LEFTPADDING",(0,0),(-1,-1),9),
                    ("RIGHTPADDING",(0,0),(-1,-1),9),
                    ("LINEBELOW",(0,0),(-1,-1),.35,border),
                ]))
                story.extend([t,Spacer(1,8)])
                continue
        heading = re.match(r"^(#{1,6})\s+(.+)$",line)
        if heading:
            story.append(Paragraph(inline(heading[2]),headings[min(len(heading[1]),3)]))
            continue
        blank = re.fullmatch(r"(.*?)_{8,}\s*",line)
        if blank:
            prefix = blank[1].strip()
            parts = [Paragraph(inline(prefix),label)] if prefix else []
            parts.extend([Spacer(1,10),HRFlowable(width="100%",thickness=.6,color=border),Spacer(1,7)])
            story.append(KeepTogether(parts))
            continue
        line = line.replace("☐","[ ]").replace("☑","[x]")
        if re.match(r"^[-*]\s+",line):
            story.append(Paragraph("• "+inline(re.sub(r"^[-*]\s+","",line)),bullet))
        else:
            story.append(Paragraph(inline(line),body))

    def cover_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(navy)
        canvas.rect(0,0,*A4,fill=1,stroke=0)
        canvas.setFillColor(teal)
        canvas.rect(0,0,9*mm,A4[1],fill=1,stroke=0)
        canvas.setFillColor(colors.HexColor("#CDE7E5"))
        canvas.setFont("Helvetica",9)
        canvas.drawString(22*mm,15*mm,"BODIVE  |  Review copy")
        canvas.restoreState()

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(border)
        canvas.line(22*mm,18*mm,188*mm,18*mm)
        canvas.setFont("Helvetica",9)
        canvas.setFillColor(muted)
        canvas.drawString(22*mm,12*mm,"BODIVE  |  Review copy")
        canvas.drawRightString(188*mm,12*mm,str(doc.page-1))
        canvas.restoreState()

    out=io.BytesIO()
    doc=SimpleDocTemplate(out,pagesize=A4,rightMargin=22*mm,leftMargin=22*mm,
                          topMargin=22*mm,bottomMargin=24*mm,title=title,author="BODIVE")
    doc.build(story,onFirstPage=cover_page,onLaterPages=footer)
    data=out.getvalue()
    if len(data)>5_000_000:
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
