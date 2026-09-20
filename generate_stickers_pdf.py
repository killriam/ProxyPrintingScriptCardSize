#!/usr/bin/env python3
"""
generate_stickers_pdf.py — Generate a DIN A4 sticker sheet with 8x18 Data Matrix barcodes.

Designed for printing compact sticker badges (7 columns × 25 rows = up to 175 stickers)
on standard DIN A4 full-sheet sticker paper or label sheets. Affix directly onto the
bottom footer of real Magic cards or card sleeves.

Usage:
    python generate_stickers_pdf.py <xml_file> [options]

Options:
    --deck-name NAME      Override the deck name for output folder and filename.
    --output-dir DIR      Custom output directory.
    --cols N              Columns per sheet (default: 7).
    --rows N              Rows per sheet (default: 25).
    --gap-x MM            Horizontal gap between stickers in mm (default: 2.0).
    --gap-y MM            Vertical gap between stickers in mm (default: 1.5).
    --skip-basic-lands    Omit basic lands.
"""

import argparse
import io
import re
import sys
from pathlib import Path

try:
    from fpdf import FPDF
except ImportError:
    print("ERROR: fpdf2 is required. Install it with:  pip install fpdf2>=2.7.0")
    sys.exit(1)

try:
    import defusedxml.ElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

try:
    from barcode_stamper import generate_barcode_badge, is_barcode_available
except ImportError:
    try:
        from .barcode_stamper import generate_barcode_badge, is_barcode_available
    except Exception:
        generate_barcode_badge = None
        is_barcode_available = lambda: False

BASIC_LAND_NAMES = {
    "Forest", "Island", "Mountain", "Plains", "Swamp",
    "Snow-Covered Forest", "Snow-Covered Island",
    "Snow-Covered Mountain", "Snow-Covered Plains", "Snow-Covered Swamp",
}

PAGE_W = 210.0   # DIN A4 width in mm
PAGE_H = 297.0   # DIN A4 height in mm

# Sticker badge dimensions (mm)
STICKER_W = 25.0
STICKER_H = 9.5
BARCODE_W = 7.5
BARCODE_H = 3.8


class StickerEntry:
    """Represents a single sticker instance to print."""
    def __init__(self, card_name: str, slot: int | None = None, optical_id: str | None = None):
        self.card_name = card_name
        self.slot = slot
        self.optical_id = optical_id


def _sanitize_xml(xml_path: Path) -> str:
    """Replace '--' inside XML comment bodies to avoid ET.ParseError."""
    text = xml_path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r'(<!--.*?)--(?=.*?-->)', r'\1-', text, flags=re.DOTALL)


def parse_sticker_entries(xml_path: Path) -> tuple[list[StickerEntry], int]:
    """
    Parse XML to extract sticker entries.
    Returns (entries, deck_id).
    """
    try:
        tree = ET.parse(xml_path)
    except Exception:
        tree = ET.parse(io.StringIO(_sanitize_xml(xml_path)))

    root = tree.getroot()
    entries: list[StickerEntry] = []
    deck_id = 1

    # Extract deck_id from printoptions if present
    print_options = root.find(".//printoptions")
    if print_options is not None:
        raw_deck_id = print_options.attrib.get("deck-id")
        if raw_deck_id and raw_deck_id.isdigit():
            deck_id = int(raw_deck_id)

    for card in root.findall(".//fronts/card"):
        name_el = card.find("name")
        if name_el is None or not name_el.text:
            continue

        filename = name_el.text.strip()
        slot_el = card.find("slot")
        opt_el = card.find("optical_id")

        slot_num: int | None = None
        if slot_el is not None and slot_el.text and slot_el.text.strip().isdigit():
            slot_num = int(slot_el.text.strip())

        opt_id: str | None = None
        if opt_el is not None and opt_el.text and opt_el.text.strip():
            opt_id = opt_el.text.strip().upper()
        elif slot_num is not None:
            # Fallback synthesis if optical_id was not populated
            opt_id = f"{deck_id:02X}{slot_num:02X}00"

        # Format display name
        display_name = filename
        for suffix in ("_normal.jpg", "_normal.png", ".jpg", ".png"):
            if display_name.lower().endswith(suffix):
                display_name = display_name[:-len(suffix)]
                break
        display_name = display_name.replace("_", " ")

        entries.append(StickerEntry(display_name, slot_num, opt_id))

    return entries, deck_id


def build_stickers_pdf(
    xml_path: Path,
    deck_name: str | None = None,
    output_dir: Path | None = None,
    cols: int = 7,
    rows: int = 25,
    gap_x: float = 2.0,
    gap_y: float = 1.5,
    skip_basic_lands: bool = False,
) -> Path:
    """Build and save the DIN A4 sticker sheet PDF."""
    if not is_barcode_available():
        raise RuntimeError("Barcode libraries (Pillow, pyStrich) are missing or incomplete.")

    raw_entries, default_deck_id = parse_sticker_entries(xml_path)

    # Filter basic lands if requested
    if skip_basic_lands:
        entries = [e for e in raw_entries if e.card_name not in BASIC_LAND_NAMES]
    else:
        entries = raw_entries

    if not entries:
        print(f"Warning: No sticker entries found in {xml_path.name}")

    # Resolve deck name
    resolved_deck = deck_name or xml_path.stem
    if resolved_deck.startswith("cards_"):
        resolved_deck = resolved_deck[6:]
    resolved_deck = re.sub(r"_\d{4}-\d{2}-\d{2}_(missing|all|owned)_(proxy|stickers)$", "", resolved_deck)

    out_folder = output_dir or (xml_path.parent / "ready2Print" / resolved_deck)
    out_folder.mkdir(parents=True, exist_ok=True)
    out_pdf = out_folder / f"{resolved_deck}_stickers.pdf"

    # Layout calculations
    per_page = cols * rows
    grid_w = cols * STICKER_W + (cols - 1) * gap_x
    grid_h = rows * STICKER_H + (rows - 1) * gap_y
    margin_x = max(2.0, (PAGE_W - grid_w) / 2.0)
    margin_y = max(6.0, (PAGE_H - grid_h) / 2.0)

    total_pages = max(1, (len(entries) + per_page - 1) // per_page)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)

    badge_cache: dict[str, io.BytesIO] = {}

    for page_idx in range(total_pages):
        pdf.add_page()

        # Header metadata
        pdf.set_font("Helvetica", "I", 6.5)
        pdf.set_text_color(120, 120, 120)
        header_text = (
            f"Deck: {resolved_deck}  |  Sheet {page_idx + 1} of {total_pages}  |  "
            f"{len(entries)} total stickers  |  8x18 Data Matrix Optical Badges"
        )
        pdf.set_xy(margin_x, margin_y - 4.5)
        pdf.cell(grid_w, 3.5, header_text, align="C")

        page_entries = entries[page_idx * per_page : (page_idx + 1) * per_page]

        for idx, item in enumerate(page_entries):
            c = idx % cols
            r = idx // cols

            x = margin_x + c * (STICKER_W + gap_x)
            y = margin_y + r * (STICKER_H + gap_y)

            # Hairline cutting border
            pdf.set_draw_color(210, 210, 210)
            pdf.set_line_width(0.12)
            pdf.rect(x, y, STICKER_W, STICKER_H)

            # Draw barcode badge on left
            if item.optical_id:
                if item.optical_id not in badge_cache:
                    badge_img = generate_barcode_badge(item.optical_id, mod_scale=8, qz_x=6, qz_y=4)
                    if badge_img is not None:
                        buf = io.BytesIO()
                        badge_img.save(buf, format="PNG")
                        buf.seek(0)
                        badge_cache[item.optical_id] = buf
                    else:
                        badge_cache[item.optical_id] = None

                cached_buf = badge_cache.get(item.optical_id)
                if cached_buf:
                    bc_x = x + 1.2
                    bc_y = y + (STICKER_H - BARCODE_H) / 2.0
                    pdf.image(cached_buf, x=bc_x, y=bc_y, w=BARCODE_W, h=BARCODE_H)

            # Draw text on right side
            text_x = x + 9.3
            text_w = STICKER_W - 10.0

            # Line 1: Slot number + Optical ID
            pdf.set_font("Helvetica", "B", 7.0)
            pdf.set_text_color(25, 25, 25)
            slot_str = f"#{item.slot}" if item.slot is not None else ""
            pdf.set_xy(text_x, y + 1.4)
            pdf.cell(8.0, 3.2, slot_str, align="L")

            if item.optical_id:
                pdf.set_font("Helvetica", "", 4.8)
                pdf.set_text_color(110, 110, 110)
                pdf.set_xy(text_x + 7.5, y + 1.5)
                pdf.cell(text_w - 7.5, 3.2, item.optical_id, align="R")

            # Line 2: Card Name (truncated if exceeds text_w)
            pdf.set_font("Helvetica", "", 5.5)
            pdf.set_text_color(40, 40, 40)
            
            # Normalize to latin-1 and truncate text to fit into text_w
            display_name = item.card_name.encode("latin-1", "replace").decode("latin-1")
            if pdf.get_string_width(display_name) > text_w:
                while len(display_name) > 1 and pdf.get_string_width(display_name + "..") > text_w:
                    display_name = display_name[:-1].rstrip()
                display_name = display_name + ".."

            pdf.set_xy(text_x, y + 5.0)
            pdf.cell(text_w, 3.0, display_name, align="L")

    pdf.output(str(out_pdf))
    print(f"Sticker sheet generated: {out_pdf} ({len(entries)} stickers, {total_pages} page(s))")
    return out_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a DIN A4 sticker sheet with 8x18 Data Matrix barcodes for MTG cards."
    )
    parser.add_argument("xml_file", help="Path to the proxy XML file from MaMo.")
    parser.add_argument("--deck-name", "-d", default=None,
                        help="Override deck name for output folder and filename.")
    parser.add_argument("--output-dir", default=None,
                        help="Custom output directory.")
    parser.add_argument("--cols", type=int, default=7,
                        help="Number of columns per sheet (default: 7).")
    parser.add_argument("--rows", type=int, default=25,
                        help="Number of rows per sheet (default: 25).")
    parser.add_argument("--gap-x", type=float, default=2.0,
                        help="Horizontal gap between stickers in mm (default: 2.0).")
    parser.add_argument("--gap-y", type=float, default=1.5,
                        help="Vertical gap between stickers in mm (default: 1.5).")
    parser.add_argument("--skip-basic-lands", action="store_true",
                        help="Omit basic lands from stickers.")

    args = parser.parse_args()

    xml_path = Path(args.xml_file)
    if not xml_path.is_absolute():
        xml_path = Path.cwd() / xml_path

    if not xml_path.exists():
        print(f"ERROR: XML file not found: {xml_path}")
        return 1

    try:
        build_stickers_pdf(
            xml_path=xml_path,
            deck_name=args.deck_name,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            cols=args.cols,
            rows=args.rows,
            gap_x=args.gap_x,
            gap_y=args.gap_y,
            skip_basic_lands=args.skip_basic_lands,
        )
        return 0
    except Exception as exc:
        print(f"ERROR: Failed to generate stickers PDF: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
