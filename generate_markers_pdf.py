#!/usr/bin/env python3
"""
generate_markers_pdf.py — Generate a DIN A4 sheet of slip-in ID markers with 8x18 Data Matrix barcodes.

Designed for printing compact slip-in markers (7 columns × 40 rows = up to 280 markers)
on standard paper or light cardstock. Cut along the guidelines and slide directly into
the bottom footer of card sleeves in front of real Magic cards.

At 3.6 mm height, markers fit completely inside the bottom black border of standard MTG
cards, leaving 100% of card artwork, rules text, and stats completely visible. No adhesive
is required.

Usage:
    python generate_markers_pdf.py <xml_file> [options]

Options:
    --deck-name NAME      Override the deck name for output folder and filename.
    --output-dir DIR      Custom output directory.
    --cols N              Columns per sheet (default: 7).
    --rows N              Rows per sheet (default: 40).
    --marker-w MM         Marker width in mm (default: 25.0 mm; use 8.0 for compact badge only).
    --gap-x MM            Horizontal gap between markers in mm (default: 2.0).
    --gap-y MM            Vertical gap between markers in mm (default: 1.5).
    --compact             Shortcut for --marker-w 8.0 (exact proxy badge size, barcode only).
    --skip-basic-lands    Omit basic lands.
"""

import argparse
import io
import re
import sys
import time
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

# Sized to match the physical proxy print ID marker in MTG bottom black footer
MARKER_H = 3.6   # Exactly 3.6 mm tall — fits within 3.8 mm card bottom border
BARCODE_W = 7.6  # 8x18 Data Matrix badge width (matching 80x38px @ 672x936)
BARCODE_H = 3.6  # 8x18 Data Matrix badge height


class MarkerEntry:
    """Represents a single slip-in marker instance to print."""
    def __init__(self, card_name: str, slot: int | None = None, optical_id: str | None = None):
        self.card_name = card_name
        self.slot = slot
        self.optical_id = optical_id


def _sanitize_xml(xml_path: Path) -> str:
    """Replace '--' inside XML comment bodies to avoid ET.ParseError."""
    text = xml_path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r'(<!--.*?)--(?=.*?-->)', r'\1-', text, flags=re.DOTALL)


def parse_marker_entries(xml_path: Path) -> tuple[list[MarkerEntry], int]:
    """
    Parse XML to extract slip-in marker entries.
    Returns (entries, deck_id).
    """
    try:
        tree = ET.parse(xml_path)
    except Exception:
        tree = ET.parse(io.StringIO(_sanitize_xml(xml_path)))

    root = tree.getroot()
    entries: list[MarkerEntry] = []
    deck_id = 1

    # Extract deck_id from printoptions if present
    print_options = root.find(".//printoptions")
    if print_options is not None:
        raw_deck_id = print_options.attrib.get("deck-id")
        if raw_deck_id and raw_deck_id.isdigit():
            deck_id = int(raw_deck_id)

    for card in root.findall(".//fronts/card"):
        name_el = card.find("name")
        card_name_el = card.find("card_name")
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
            opt_id = opt_el.text.strip()
        elif slot_num is not None:
            # Clean slot-only payload
            opt_id = str(slot_num)

        # If slot was not explicitly set in <slot>, extract from optical_id
        if slot_num is None and opt_id:
            if opt_id.isdigit():
                slot_num = int(opt_id)
            elif len(opt_id) == 6:
                try:
                    slot_num = int(opt_id[2:4], 16)
                except ValueError:
                    pass

        # Format display name: prefer <card_name> tag if present
        if card_name_el is not None and card_name_el.text and card_name_el.text.strip():
            display_name = card_name_el.text.strip()
        else:
            display_name = filename
            for suffix in ("_normal.jpg", "_normal.png", ".jpg", ".png"):
                if display_name.lower().endswith(suffix):
                    display_name = display_name[:-len(suffix)]
                    break
            display_name = re.sub(r"_[a-z0-9]{3,4}_\w+$", "", display_name)
            display_name = display_name.replace("_", " ")

        entries.append(MarkerEntry(display_name, slot_num, opt_id))

    return entries, deck_id


def build_markers_pdf(
    xml_path: Path,
    deck_name: str | None = None,
    output_dir: Path | None = None,
    cols: int = 4,
    rows: int = 45,
    marker_w: float = 12.0,
    name_w: float = 32.0,
    gap_x: float = 3.0,
    gap_y: float = 2.0,
    skip_basic_lands: bool = False,
    show_names: bool = True,
    cut_marks: bool = True,
) -> Path:
    """Build and save the DIN A4 slip-in ID markers sheet PDF with orientation card names and cut marks."""
    if not is_barcode_available():
        raise RuntimeError("Barcode libraries (Pillow, pyStrich) are missing or incomplete.")

    raw_entries, default_deck_id = parse_marker_entries(xml_path)

    # Filter basic lands if requested
    if skip_basic_lands:
        entries = [e for e in raw_entries if e.card_name not in BASIC_LAND_NAMES]
    else:
        entries = raw_entries

    if not entries:
        print(f"Warning: No marker entries found in {xml_path.name}")

    # Resolve deck name
    resolved_deck = deck_name or xml_path.stem
    if resolved_deck.startswith("cards_"):
        resolved_deck = resolved_deck[6:]
    resolved_deck = re.sub(r"_\d{4}-\d{2}-\d{2}_(missing|all|owned)_(proxy|markers|stickers)$", "", resolved_deck)

    out_folder = output_dir or (xml_path.parent / "ready2Print" / resolved_deck)
    out_folder.mkdir(parents=True, exist_ok=True)
    out_pdf = out_folder / f"{resolved_deck}_markers.pdf"

    # Layout calculations
    cell_w = marker_w + (1.2 + name_w if show_names else 0.0)
    per_page = cols * rows
    grid_w = cols * cell_w + (cols - 1) * gap_x
    grid_h = rows * MARKER_H + (rows - 1) * gap_y
    margin_x = max(4.0, (PAGE_W - grid_w) / 2.0)
    margin_y = max(10.0, (PAGE_H - grid_h) / 2.0)

    total_pages = max(1, (len(entries) + per_page - 1) // per_page)

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(False)

    badge_cache: dict[str, io.BytesIO] = {}

    for page_idx in range(total_pages):
        pdf.add_page()
        page_entries = entries[page_idx * per_page : (page_idx + 1) * per_page]
        rows_active = min(rows, (len(page_entries) + cols - 1) // cols)
        active_h = rows_active * MARKER_H + (rows_active - 1) * gap_y

        # Header metadata
        pdf.set_font("Helvetica", "B", 7.5)
        pdf.set_text_color(30, 41, 59)
        header_text = (
            f"Deck: {resolved_deck}   |   Slip-in ID Markers   |   Sheet {page_idx + 1} of {total_pages}   ({len(entries)} markers)"
        )
        pdf.set_xy(margin_x, margin_y - 12.0 if cut_marks else margin_y - 10.0)
        pdf.cell(grid_w, 3.5, header_text, align="C")

        pdf.set_font("Helvetica", "I", 6.0)
        pdf.set_text_color(100, 116, 139)
        if cut_marks:
            sub_text = (
                "Cut out solid slips (12 x 3.6 mm). Use perimeter cut marks & corner registration marks for cutting devices and trimmers."
                if show_names else
                "Cut out solid slips (8 x 3.6 mm). Use perimeter cut marks & corner registration marks for cutting devices and trimmers."
            )
        else:
            sub_text = (
                "Cut out the solid rectangle slips (12 x 3.6 mm) for card sleeves. "
                "Card names on the right are for orientation only (do not cut out)."
            )
        pdf.set_xy(margin_x, margin_y - 8.2 if cut_marks else margin_y - 6.2)
        pdf.cell(grid_w, 3.0, sub_text, align="C")

        if cut_marks:
            # 1. Optical Registration Marks for cutting plotters (Cricut, Silhouette, Brother ScanNCut)
            reg_size = 5.0
            pdf.set_fill_color(0, 0, 0)
            pdf.set_draw_color(0, 0, 0)
            pdf.set_line_width(0.5)

            # Top-Left: Solid square fiducial (plotter origin)
            pdf.rect(margin_x - 6.0, margin_y - 6.0, reg_size, reg_size, style="F")

            # Top-Right: L-bracket
            tr_x = margin_x + grid_w + 1.0
            tr_y = margin_y - 6.0
            pdf.line(tr_x, tr_y, tr_x + reg_size, tr_y)
            pdf.line(tr_x + reg_size, tr_y, tr_x + reg_size, tr_y + reg_size)

            # Bottom-Left: L-bracket
            bl_x = margin_x - 6.0
            bl_y = margin_y + grid_h + 1.0
            pdf.line(bl_x, bl_y, bl_x, bl_y + reg_size)
            pdf.line(bl_x, bl_y + reg_size, bl_x + reg_size, bl_y + reg_size)

            # Bottom-Right: L-bracket
            br_x = margin_x + grid_w + 1.0
            br_y = margin_y + grid_h + 1.0
            pdf.line(br_x + reg_size, br_y, br_x + reg_size, br_y + reg_size)
            pdf.line(br_x, br_y + reg_size, br_x + reg_size, br_y + reg_size)

            # 2. Margin Trimmer Cut Marks (for rotary cutters & guillotines)
            pdf.set_draw_color(15, 23, 42)
            pdf.set_line_width(0.18)

            # Vertical cut marks (Top margin and bottom of active rows + bottom of page)
            for c in range(cols):
                col_x = margin_x + c * (cell_w + gap_x)
                for x in (col_x, col_x + marker_w):
                    # Top margin tick
                    pdf.line(x, margin_y - 1.0, x, margin_y - 4.5)
                    # Directly below active rows
                    pdf.line(x, margin_y + active_h + 1.0, x, margin_y + active_h + 4.5)
                    # Bottom of grid (if page isn't completely filled)
                    if active_h < grid_h - 10:
                        pdf.line(x, margin_y + grid_h + 1.0, x, margin_y + grid_h + 4.5)

            # Horizontal cut marks (Left & Right margins for each active row)
            for r in range(rows_active):
                row_y = margin_y + r * (MARKER_H + gap_y)
                for y_pos in (row_y, row_y + MARKER_H):
                    pdf.line(margin_x - 1.0, y_pos, margin_x - 4.5, y_pos)
                    pdf.line(margin_x + grid_w + 1.0, y_pos, margin_x + grid_w + 4.5, y_pos)
        else:
            # Column labels
            pdf.set_font("Helvetica", "B", 5.5)
            pdf.set_text_color(148, 163, 184)
            for c in range(cols):
                col_x = margin_x + c * (cell_w + gap_x)
                pdf.set_xy(col_x, margin_y - 3.2)
                pdf.cell(marker_w, 2.5, "CUT SLIP", align="C")
                if show_names:
                    pdf.set_xy(col_x + marker_w + 1.2, margin_y - 3.2)
                    pdf.cell(name_w, 2.5, "CARD NAME (ORIENTATION)", align="L")

        for idx, item in enumerate(page_entries):
            c = idx % cols
            r = idx // cols

            cell_x = margin_x + c * (cell_w + gap_x)
            y = margin_y + r * (MARKER_H + gap_y)

            # Hairline cutting border around marker ONLY
            pdf.set_draw_color(71, 85, 105)
            pdf.set_line_width(0.15)
            pdf.rect(cell_x, y, marker_w, MARKER_H)

            # Render barcode badge
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
                    bc_x = cell_x + 0.2
                    bc_y = y
                    pdf.image(cached_buf, x=bc_x, y=bc_y, w=BARCODE_W, h=BARCODE_H)

            # Number-only text section inside the cut box (strictly slot number e.g. "#15")
            if marker_w > BARCODE_W + 1.5:
                text_x = cell_x + BARCODE_W + 0.2
                text_w = marker_w - BARCODE_W - 0.4
                slot_str = f"#{item.slot}" if item.slot is not None else ""

                pdf.set_font("Helvetica", "B", 6.2)
                pdf.set_text_color(15, 23, 42)
                pdf.set_xy(text_x, y + 0.3)
                pdf.cell(text_w, 3.0, slot_str, align="C")

            # Orientation card name outside the cut box
            if show_names and item.card_name:
                name_x = cell_x + marker_w + 1.2
                pdf.set_font("Helvetica", "", 6.5)
                pdf.set_text_color(30, 41, 59)
                card_title = item.card_name
                while pdf.get_string_width(card_title + "...") > name_w and len(card_title) > 3:
                    card_title = card_title[:-1]
                if card_title != item.card_name:
                    card_title += "..."
                pdf.set_xy(name_x, y + 0.3)
                pdf.cell(name_w, 3.0, card_title, align="L")

    try:
        pdf.output(str(out_pdf))
    except PermissionError:
        alt_pdf = out_folder / f"{resolved_deck}_markers_{int(time.time())}.pdf"
        print(f"  Note: {out_pdf.name} is currently open in another program. Saved as {alt_pdf.name}")
        pdf.output(str(alt_pdf))
        out_pdf = alt_pdf

    print(f"Slip-in ID markers sheet generated: {out_pdf} ({len(entries)} markers, {total_pages} page(s))")
    return out_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a DIN A4 sheet of slip-in ID markers with 8x18 Data Matrix barcodes for MTG cards."
    )
    parser.add_argument("xml_file", help="Path to the proxy XML file from MaMo.")
    parser.add_argument("--deck-name", "-d", default=None,
                        help="Override deck name for output folder and filename.")
    parser.add_argument("--output-dir", default=None,
                        help="Custom output directory.")
    parser.add_argument("--cols", type=int, default=4,
                        help="Number of columns per sheet (default: 4).")
    parser.add_argument("--rows", type=int, default=45,
                        help="Number of rows per sheet (default: 45).")
    parser.add_argument("--marker-w", type=float, default=12.0,
                        help="Marker cut box width in mm (default: 12.0).")
    parser.add_argument("--name-w", type=float, default=32.0,
                        help="Orientation card name width in mm (default: 32.0).")
    parser.add_argument("--compact", action="store_true",
                        help="Compact mode: dense grid of barcodes without orientation card names.")
    parser.add_argument("--gap-x", type=float, default=3.0,
                        help="Horizontal gap between columns in mm (default: 3.0).")
    parser.add_argument("--gap-y", type=float, default=2.0,
                        help="Vertical gap between markers in mm (default: 2.0).")
    parser.add_argument("--skip-basic-lands", action="store_true",
                        help="Omit basic lands from markers.")
    parser.add_argument("--cut-marks", action="store_true", default=True,
                        help="Draw cutting marks (perimeter trimmer ticks & corner plotter registration fiducials). Default: enabled.")
    parser.add_argument("--no-cut-marks", action="store_false", dest="cut_marks",
                        help="Disable cutting marks.")

    args = parser.parse_args()

    xml_path = Path(args.xml_file)
    if not xml_path.is_absolute():
        xml_path = Path.cwd() / xml_path

    if not xml_path.exists():
        print(f"ERROR: XML file not found: {xml_path}")
        return 1

    show_names = not args.compact
    cols = 12 if args.compact else args.cols
    marker_width = 8.0 if args.compact else args.marker_w

    try:
        build_markers_pdf(
            xml_path=xml_path,
            deck_name=args.deck_name,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            cols=cols,
            rows=args.rows,
            marker_w=marker_width,
            name_w=args.name_w,
            gap_x=args.gap_x,
            gap_y=args.gap_y,
            skip_basic_lands=args.skip_basic_lands,
            show_names=show_names,
            cut_marks=args.cut_marks,
        )
        return 0
    except Exception as exc:
        print(f"ERROR: Failed to generate markers PDF: {exc}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
