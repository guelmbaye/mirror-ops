#!/usr/bin/env python3
"""Builds the two-page brief attached to the Devpost submission.

A judge comparing dozens of projects reads a page, not a repository. This sheet
carries only what cannot be grasped from the video: the differentiation matrix,
where YouCam sits in the decision loop, and the limits we state ourselves.

    python scripts/build_onepager.py

Output: mirror-ops-onepager.pdf at the repository root.
"""

from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageBreak,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT / "apps" / "api", ROOT):
    if (candidate / "app").is_dir():
        sys.path.insert(0, str(candidate))
        break

# Brand palette, taken from the logo (see apps/web/src/app/globals.css).
PORCELAIN = colors.HexColor("#F0F1F3")
INK = colors.HexColor("#0B1A2E")
NAVY = colors.HexColor("#0A326E")
GRAPHITE = colors.HexColor("#5C6675")
MERCURY = colors.HexColor("#D3D6DC")
SIGNAL = colors.HexColor("#C1005C")

LOGO = ROOT / "apps" / "web" / "public" / "logo-mirror-ops@2x.png"


def styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "base", fontName="Helvetica", fontSize=9.2, leading=13.2,
        textColor=INK, alignment=TA_LEFT,
    )
    return {
        "body": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=GRAPHITE),
        "lead": ParagraphStyle("lead", parent=base, fontSize=11, leading=15.5),
        "signature": ParagraphStyle(
            "signature", parent=base, fontName="Helvetica-Bold",
            fontSize=17, leading=20, textColor=INK, spaceAfter=2,
        ),
        "tagline": ParagraphStyle(
            "tagline", parent=base, fontSize=10, leading=14,
            textColor=SIGNAL, spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "h", parent=base, fontName="Helvetica-Bold", fontSize=8,
            leading=11, textColor=SIGNAL, spaceBefore=11, spaceAfter=4,
        ),
        "cell": ParagraphStyle("cell", parent=base, fontSize=8.4, leading=11.4),
        "cellmuted": ParagraphStyle(
            "cellmuted", parent=base, fontSize=8.4, leading=11.4, textColor=GRAPHITE
        ),
    }


def rule() -> Table:
    line = Table([[""]], colWidths=[170 * mm], rowHeights=[0.5])
    line.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), MERCURY)]))
    return line


def matrix(s: dict) -> Table:
    """The measurement that proves the thesis: same look, different verdicts."""
    header = ["", "wedding", "interview", "dinner", "travel"]
    # Produit par exactement ce que l'interface envoie. Regenerer apres toute
    # modification des tables du moteur : un chiffre verifiable en une seconde
    # est le pire endroit ou se tromper.
    rows = [
        ["casual", ("MISMATCH", 47), ("MISMATCH", 46), ("ALMOST", 60), ("ALMOST", 69)],
        ["in between", ("ALMOST", 64), ("ALMOST", 64), ("FIT", 74), ("ALMOST", 67)],
        ["dressed up", ("FIT", 81), ("FIT", 81), ("ALMOST", 68), ("ALMOST", 60)],
    ]

    data = [[Paragraph(f"<b>{h}</b>" if h else "", s["cell"]) for h in header]]
    highlights: list[tuple[int, int]] = []
    for r, (label, *cells) in enumerate(rows, start=1):
        line = [Paragraph(f"<b>{label}</b>", s["cell"])]
        for c, (state, score) in enumerate(cells, start=1):
            strong = state == "FIT" or state == "MISMATCH"
            if strong:
                highlights.append((c, r))
            line.append(Paragraph(f"{state}<br/><font size=7>{score}</font>", s["cell"]))
        data.append(line)

    table = Table(data, colWidths=[26 * mm] + [36 * mm] * 4)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, MERCURY),
        ("LINEBELOW", (0, 1), (-1, -2), 0.3, PORCELAIN),
        ("BACKGROUND", (0, 0), (-1, 0), PORCELAIN),
    ]
    for col, row in highlights:
        style.append(("BACKGROUND", (col, row), (col, row), colors.HexColor("#FCEAF1")))
    table.setStyle(TableStyle(style))
    return table


def two_columns(s: dict, left: list, right: list) -> Table:
    table = Table([[left, right]], colWidths=[83 * mm, 83 * mm])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 8),
    ]))
    return table


def page_one(s: dict) -> list:
    story: list = []

    if LOGO.exists():
        logo = Image(str(LOGO), width=46 * mm, height=46 * mm * 251 / 835)
        logo.hAlign = "LEFT"
        story += [logo, Spacer(1, 7)]

    story += [
        Paragraph("Fit the moment. One change.", s["signature"]),
        Paragraph("Contextual appearance decision engine", s["tagline"]),
        Paragraph(
            "You have ten minutes before an interview. You don't need twenty outfit "
            "ideas — you need to know whether what you're wearing works, and if not, "
            "what single thing to change. Every appearance tool answers <i>what should "
            "I wear?</i> MIRROR OPS answers <b>will this look work here?</b>",
            s["lead"],
        ),
        Spacer(1, 8),
        rule(),
        Paragraph("THE THESIS, MEASURED", s["h"]),
        Paragraph(
            "The same look, judged against four different moments. The diagonal is the "
            "product — including <i>overdressed for travel</i>, which is a mismatch too.",
            s["muted"],
        ),
        Spacer(1, 5),
        matrix(s),
        Spacer(1, 4),
        Paragraph(
            "Contextual fit score 0–100, computed before any change is proposed. "
            "A casual look scores 69 for travel and 47 for a wedding.",
            s["muted"],
        ),
        Paragraph("THE JOURNEY — UNDER 90 SECONDS", s["h"]),
        Preformatted(
            "MOMENT  →  CURRENT LOOK  →  CONTEXTUAL FIT  →  ONE CHANGE  →  PROOF  →  ACT\n"
            "occasion,   photo +          FIT / ALMOST /     the decisive   YouCam    you\n"
            "goal, time  YouCam Skin AI   MISMATCH           lever          VTO       leave",
            ParagraphStyle("mono", fontName="Courier", fontSize=7.4, leading=10.4, textColor=NAVY),
        ),
        Spacer(1, 3),
    ]

    left = [
        Paragraph("ONE CHANGE, NEVER A LIST", s["h"]),
        Paragraph(
            "A single intervention, chosen from a closed space of eight actions. It can "
            "<b>change</b> a piece, <b>add</b> one that is missing, or <b>remove</b> one "
            "too many — and it always states what stays.", s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "<b>NO CHANGE is a real outcome</b> and consumes no try-on credit. A decision "
            "engine that cannot decide to do nothing is a recommendation generator.",
            s["body"],
        ),
    ]
    right = [
        Paragraph("WHAT IT IS NOT", s["h"]),
        Paragraph(
            "Not an AI stylist. Not a shopping assistant. Not a wardrobe manager. "
            "Not a try-on app. Not a skin diagnostic tool.", s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "No catalogue to browse, no list to compare, no chatbot. One moment in, "
            "one decision out. <b>The constraint is the product.</b>", s["body"],
        ),
    ]
    story += [two_columns(s, left, right), Spacer(1, 9), rule()]
    story += youcam_diagram(s)
    return story


def youcam_diagram(s: dict) -> list:
    return [
        Paragraph("WHERE YOUCAM SITS", s["h"]),
        Paragraph(
            "Inside the decision loop, not beside it. The browser never talks to the "
            "provider; the key stays server-side.", s["muted"],
        ),
        Spacer(1, 5),
        Preformatted(
            "                 .... face crop, 68% width ....>  SKIN AI      informs the decision\n"
            "  ONE PHOTO .....:                                             influence capped at 0.08\n"
            "                 '.... original image .........>  APPAREL VTO  proves the decision\n"
            "                                                               winner only, 1 per journey",
            ParagraphStyle("mono2", fontName="Courier", fontSize=7, leading=10.5, textColor=NAVY),
        ),
    ]


def page_two(s: dict) -> list:
    story: list = [Paragraph("HOW THE INTEGRATION HOLDS UP", s["h"]), Spacer(1, 2)]

    facts = [
        ("Skin AI needs a close-up; we photograph an outfit.",
         "It rejects images where the face fills under 60% of the width. Asking for a "
         "second photo would have added a screen to a 90-second flow, so the server "
         "crops the face from the same shot. The original goes untouched to the try-on."),
        ("YouCam returns health scores; the engine reasons in severity.",
         "Redness, oiliness and texture are inverted on the way in. Without that, "
         "flawless skin would read as heavily marked and push the decision the wrong way."),
        ("One journey costs one analysis and one try-on.",
         "Candidates are scored, only the winner is rendered. Enforced by input-aware "
         "idempotency keys and by a test that counts provider calls."),
        ("A failure never fakes a success.",
         "Offline previews are watermarked and flagged simulated: true all the way to "
         "the UI. If Skin AI is unavailable, the journey continues without it, says so, "
         "and lowers its stated confidence."),
    ]
    rows = [
        [Paragraph(f"<b>{title}</b><br/>{body}", s["cell"])]
        for title, body in facts
    ]
    table = Table(rows, colWidths=[170 * mm])
    table.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBEFORE", (0, 0), (0, -1), 1.6, SIGNAL),
        ("LINEBELOW", (0, 0), (-1, -2), 0.3, MERCURY),
    ]))
    story += [table, Spacer(1, 4)]

    left = [
        Paragraph("VERIFIED, NOT ASSUMED", s["h"]),
        Paragraph(
            "233 backend tests · 28 frontend tests · a 38-check end-to-end audit against "
            "the assembled system.", s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "The audit catches what unit tests cannot: a piece declared absent listed as "
            "“kept”, a FIT verdict beside a demanded change, media URLs that return 201 "
            "and show nothing.", s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "Live try-on confirmed end to end: <b>simulated: false</b>, 14.4 s, on a real "
            "YouCam render.", s["body"],
        ),
    ]
    right = [
        Paragraph("LIMITS WE STATE OURSELVES", s["h"]),
        Paragraph(
            "On a full-length shot the face is often too small even after cropping, so "
            "the skin signal is frequently absent. The journey continues and says so.",
            s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "There is no user feedback on the decision yet — the one signal that would "
            "let the scoring be calibrated on evidence rather than judgement.", s["body"],
        ),
        Spacer(1, 4),
        Paragraph(
            "We do <b>not</b> claim reduced returns. It is a plausible second-order "
            "effect, and we have no evidence for it.", s["body"],
        ),
    ]
    story += [two_columns(s, left, right), Spacer(1, 8), rule(), Spacer(1, 5)]

    story += [
        Paragraph("RETAIL VALUE", s["h"]),
        Paragraph(
            "The decision layer is the product; a catalogue is only an input. A "
            "retailer's existing product visuals become MIRROR OPS garments through a "
            "manifest of <font face='Courier' size='8'>id → URL</font>, imported in one "
            "command with no further integration. That places the try-on at the moment "
            "of <b>hesitation</b> rather than the moment of browsing: uncertainty → one "
            "change → visual proof → decision confidence.", s["body"],
        ),
        Spacer(1, 10),
        rule(),
        Spacer(1, 6),
        Paragraph("WHAT A JUDGE SHOULD TAKE AWAY", s["h"]),
        Paragraph(
            "<b>“That AI made a decision for me.”</b> &nbsp;Not: “that app calls a "
            "try-on API.” The three moments that carry it: "
            "<font color='#C1005C'><b>ALMOST THERE</b></font> &nbsp;→&nbsp; "
            "<font color='#C1005C'><b>BEFORE / AFTER</b></font> &nbsp;→&nbsp; "
            "<font color='#C1005C'><b>EVERYTHING ELSE STAYS</b></font>", s["lead"],
        ),
        Spacer(1, 8),
        Paragraph(
            "Repository, demo and video links are on the Devpost submission page. "
            "Source, tests, deployment guide and the full positioning document ship "
            "with the code.", s["muted"],
        ),
    ]
    return story


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(GRAPHITE)
    canvas.drawString(20 * mm, 12 * mm, "MIRROR OPS — YouCam API Hackathon")
    canvas.drawRightString(190 * mm, 12 * mm, f"{doc.page}/2")
    canvas.setStrokeColor(MERCURY)
    canvas.setLineWidth(0.4)
    canvas.line(20 * mm, 15.5 * mm, 190 * mm, 15.5 * mm)
    canvas.restoreState()


def main() -> int:
    output = ROOT / "mirror-ops-onepager.pdf"
    doc = BaseDocTemplate(
        str(output), pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title="MIRROR OPS — Fit the moment. One change.",
        author="MIRROR OPS",
        subject="Contextual appearance decision engine — YouCam API Hackathon",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=footer)])

    s = styles()
    doc.build(page_one(s) + [PageBreak()] + page_two(s))
    print(f"Written: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
