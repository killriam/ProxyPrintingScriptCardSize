#!/usr/bin/env python3
"""
generate_a4_pdf.py — Generate a DIN A4 PDF with 9 MTG proxy cards per page.

Cards are laid out in a 3×3 grid of 63×88 mm each, centered on A4 (210×297 mm).
This matches mtgprint.net behavior — print at 100% scale / actual size.

Usage:
    python generate_a4_pdf.py <xml_file> [options]

Options:
    --gap {0,0.2,3}     Gap in mm between cards (default: 0.2).
    --cut-marks         Draw 3 mm cut marks at each card corner.
    --watermark         Print "Playtest Card" diagonally across each card.
    --skip-basic-lands  Omit basic land cards (Forest/Island/Mountain/Plains/Swamp).
    --deck-name NAME    Override the deck name for image lookup and output path.
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("ERROR: fpdf2 is required. Install it with:  pip install fpdf2>=2.7.0")
    sys.exit(1)

BASIC_LAND_NAMES = {
    "Forest", "Island", "Mountain", "Plains", "Swamp",
    "Snow-Covered Forest", "Snow-Covered Island",
    "Snow-Covered Mountain", "Snow-Covered Plains", "Snow-Covered Swamp",
}

# Card dimensions (mm)
CARD_W = 63.0
CARD_H = 88.0
PAGE_W = 210.0   # A4
PAGE_H = 297.0   # A4
COLS = 3
ROWS = 3


def parse_card_names(xml_path: Path) -> list[str]:
    """Return list of card image filenames from <cardpacks><fronts><card><name>."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    names = []
    for card in root.findall(".//fronts/card"):
        name_el = card.find("name")
        if name_el is not None and name_el.text:
            names.append(name_el.text.strip())
    return names


def card_display_name(filename: str) -> str:
    """Strip _normal.jpg suffix and convert underscores to spaces for display."""
    name = filename
    for suffix in ("_normal.jpg", "_normal.png", ".jpg", ".png"):
        if name.lower().endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name.replace("_", " ")


def build_pdf(
    xml_path: Path,
    gap: float,
    cut_marks: bool,
    watermark: bool,
    skip_basic_lands: bool,
    deck_name: str | None = None,
) -> Path:
    deck = deck_name or xml_path.stem
    if deck.startswith("cards_"):
        deck = deck[6:]

    xml_dir = xml_path.parent
    image_dir = xml_dir / "mtg" / "images" / deck
    output_dir = xml_dir / "ready2Print" / deck
    output_dir.mkdir(parents=True, exist_ok=True)

    card_names = parse_card_names(xml_path)

    if skip_basic_lands:
        card_names = [n for n in card_names if card_display_name(n) not in BASIC_LAND_NAMES]

    if not card_names:
        print("WARNING: No cards to print after applying filters.")

    # Centered margins with gap between cards
    x_margin = (PAGE_W - COLS * CARD_W - (COLS - 1) * gap) / 2
    y_margin = (PAGE_H - ROWS * CARD_H - (ROWS - 1) * gap) / 2

    pdf = FPDF(unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.set_font("Helvetica", size=7)

    per_page = COLS * ROWS
    for page_idx in range(0, max(1, len(card_names)), per_page):
        pdf.add_page()
        page_cards = card_names[page_idx : page_idx + per_page]

        for slot, img_name in enumerate(page_cards):
            row = slot // COLS
            col = slot % COLS
            x = x_margin + col * (CARD_W + gap)
            y = y_margin + row * (CARD_H + gap)

            img_path = image_dir / img_name
            if img_path.exists():
                try:
                    pdf.image(str(img_path), x=x, y=y, w=CARD_W, h=CARD_H)
                except Exception as exc:
                    print(f"  WARNING: Could not embed {img_name}: {exc}")
                    _draw_placeholder(pdf, x, y, img_name)
            else:
                print(f"  WARNING: Image not found: {img_path.name}")
                _draw_placeholder(pdf, x, y, img_name)

            if cut_marks:
                _draw_cut_marks(pdf, x, y)
            if watermark:
                _draw_watermark(pdf, x, y)

    output_path = output_dir / f"{deck}_a4.pdf"
    pdf.output(str(output_path))
    return output_path


def _draw_placeholder(pdf: FPDF, x: float, y: float, img_name: str) -> None:
    """Draw a gray placeholder rectangle with card name when image is missing."""
    pdf.set_fill_color(220, 220, 220)
    pdf.rect(x, y, CARD_W, CARD_H, style="F")
    pdf.set_draw_color(150, 150, 150)
    pdf.rect(x, y, CARD_W, CARD_H, style="D")
    display = card_display_name(img_name)
    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Helvetica", size=7)
    pdf.set_xy(x, y + CARD_H / 2 - 3)
    pdf.cell(CARD_W, 6, txt=display, align="C")
    pdf.set_text_color(0, 0, 0)


def _draw_cut_marks(pdf: FPDF, x: float, y: float, mark_len: float = 3.0) -> None:
    """Draw hairline cut marks at all four corners of a card."""
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.1)
    x2 = x + CARD_W
    y2 = y + CARD_H
    # Top-left
    pdf.line(x - mark_len, y, x, y)
    pdf.line(x, y - mark_len, x, y)
    # Top-right
    pdf.line(x2, y, x2 + mark_len, y)
    pdf.line(x2, y - mark_len, x2, y)
    # Bottom-left
    pdf.line(x - mark_len, y2, x, y2)
    pdf.line(x, y2, x, y2 + mark_len)
    # Bottom-right
    pdf.line(x2, y2, x2 + mark_len, y2)
    pdf.line(x2, y2, x2, y2 + mark_len)


def _draw_watermark(pdf: FPDF, x: float, y: float) -> None:
    """Draw diagonal 'Playtest Card' text across the card."""
    pdf.set_text_color(200, 200, 200)
    pdf.set_font("Helvetica", style="B", size=10)
    cx = x + CARD_W / 2
    cy = y + CARD_H / 2
    with pdf.rotation(35, cx, cy):
        pdf.set_xy(cx - 18, cy - 3)
        pdf.cell(36, 6, txt="Playtest Card", align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=7)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a DIN A4 proxy PDF (9 cards/page) from a MaMo proxy XML."
    )
    parser.add_argument("xml_file", help="Path to the proxy XML file.")
    parser.add_argument("--deck-name", "-d", default=None,
                        help="Override deck name for image lookup and output path.")
    parser.add_argument("--gap", choices=["0", "0.2", "3"], default="0.2",
                        help="Gap in mm between cards (default: 0.2).")
    parser.add_argument("--cut-marks", action="store_true",
                        help="Draw 3 mm cut marks at each card corner.")
    parser.add_argument("--watermark", action="store_true",
                        help="Add diagonal 'Playtest Card' text across each card.")
    parser.add_argument("--skip-basic-lands", action="store_true",
                        help="Omit basic land cards (Forest/Island/Mountain/Plains/Swamp).")
    args = parser.parse_args()

    xml_path = Path(args.xml_file)
    if not xml_path.is_absolute():
        xml_path = Path.cwd() / xml_path
    if not xml_path.exists():
        print(f"ERROR: XML file not found: {xml_path}")
        return 1

    print(f"Generating A4 PDF from: {xml_path.name}")
    try:
        output = build_pdf(
            xml_path,
            gap=float(args.gap),
            cut_marks=args.cut_marks,
            watermark=args.watermark,
            skip_basic_lands=args.skip_basic_lands,
            deck_name=args.deck_name,
        )
        print(f"  PDF created: {output}")
        return 0
    except Exception as exc:
        print(f"  ERROR: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
