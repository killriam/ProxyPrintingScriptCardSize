#!/usr/bin/env python3
"""
proxy_print.py — MaMo one-command proxy print pipeline

Steps:
  1. Download card images from Scryfall       (download_card_images.py)
  2. Build multi-page front card SLA          (simple_multi_page.py)
  3. (optional) Build background SLA          (--background <image>)
  4. (optional) Export SLA file(s) to PDF     (--pdf)

Usage:
    python proxy_print.py <xml_file> [options]

Options:
    --deck-name, -d     Override deck name (default: derived from XML filename).
    --scribus, -s       Path to Scribus executable (default: auto-detect or SCRIBUS_CMD env var).
    --background, -b    Path to a background/cardback image file (any format Scribus can open).
                        Creates a second SLA with that image repeated once per card.
    --pdf               Automatically export all produced SLA files to PDF.
    --create-cardback   (legacy) Generate a cardback SLA from the XML <cardback> element.

Examples:
    python proxy_print.py my_deck.xml
    python proxy_print.py my_deck.xml --background "C:\\path\\to\\back.png" --pdf
    python proxy_print.py my_deck.xml --scribus "C:\\Program Files\\Scribus 1.6.5\\Scribus.exe"
"""

import argparse
import os
import re
import shutil
import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

# Default Scribus locations to probe (Windows)
SCRIBUS_CANDIDATES = [
    r"C:\Program Files\Scribus 1.6.5\Scribus.exe",
    r"C:\Program Files\Scribus 1.6.4\Scribus.exe",
    r"C:\Program Files\Scribus 1.6.3\Scribus.exe",
    r"C:\Program Files\Scribus 1.6.2\Scribus.exe",
    r"C:\Program Files\Scribus 1.6.1\Scribus.exe",
    r"C:\Program Files\Scribus 1.6.0\Scribus.exe",
    r"C:\Program Files\Scribus 1.5\Scribus.exe",
    r"C:\Program Files (x86)\Scribus\Scribus.exe",
    "scribus",  # on PATH (Linux/macOS)
]


def find_scribus() -> str | None:
    """Return the first usable Scribus executable path, or None."""
    env_cmd = os.environ.get("SCRIBUS_CMD")
    if env_cmd:
        return env_cmd
    for candidate in SCRIBUS_CANDIDATES:
        p = Path(candidate)
        if p.is_absolute():
            if p.exists():
                return str(p)
        else:
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0 or "scribus" in (result.stdout + result.stderr).lower():
                    return candidate
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
    return None


def sanitize_xml(xml_path: Path) -> str:
    """
    Return the XML file content with any '--' inside comment bodies replaced
    by '-' so that ET.parse does not raise 'not well-formed (invalid token)'.
    The '--' sequence is forbidden inside XML comments by the XML 1.0 spec.
    """
    text = xml_path.read_text(encoding="utf-8", errors="replace")
    return re.sub(r'(<!--.*?)--(?=.*?-->)', r'\1-', text, flags=re.DOTALL)


def count_cards_in_xml(xml_path: Path) -> int:
    """Return the number of <card> entries in the <fronts> section of the proxy XML."""
    try:
        try:
            root = ET.parse(str(xml_path)).getroot()
        except ET.ParseError:
            import io
            root = ET.parse(io.StringIO(sanitize_xml(xml_path))).getroot()
        fronts = root.find("fronts")
        return len(list(fronts.findall("card"))) if fronts is not None else 0
    except Exception:
        return 0


def update_all_pfile_paths(sla_path: Path, image_path: str) -> bool:
    """Replace every PFILE="..." value in the SLA file with *image_path*."""
    try:
        content = sla_path.read_text(encoding="utf-8")
        new_content = re.sub(r'PFILE="[^"]*"', f'PFILE="{image_path}"', content)
        sla_path.write_text(new_content, encoding="utf-8")
        return True
    except Exception as e:
        print(f"  Warning: failed to update PFILE paths: {e}")
        return False


def build_background_sla(
    xml_path: Path,
    background_image: Path,
    output_dir: Path,
    deck_name: str,
    scribus_cmd: str,
    script_dir: Path,
) -> "Path | None":
    """
    Build a multi-page Scribus SLA with *background_image* on every page.

    The number of pages matches the card count in the XML so that the
    background SLA can be printed back-to-back with the front SLA.
    Returns the SLA path on success, None on failure.
    """
    card_count = count_cards_in_xml(xml_path)
    if card_count == 0:
        print("  ERROR: No cards found in XML, cannot build background SLA.")
        return None

    template_path = script_dir / "scribus_template_proxy.sla"
    copy_script = script_dir / "copy_slaTemplate.py"
    sla_out = output_dir / f"{deck_name}_background.sla"
    output_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(template_path, sla_out)
    print(f"  Template copied → {sla_out}")

    if card_count > 1:
        copies = card_count - 1
        cmd = [scribus_cmd, str(sla_out), "-g", "-ns",
               "--python-script", str(copy_script), str(copies)]
        print(f"  Running Scribus to add {copies} pages...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout.strip():
            print(result.stdout)
        if result.returncode != 0:
            print(f"  ERROR: Scribus page duplication failed:\n{result.stderr}")
            return None

    # Use the absolute path of the background image (forward slashes for SLA compat)
    bg_path_str = str(background_image.resolve()).replace("\\", "/")
    update_all_pfile_paths(sla_out, bg_path_str)
    print(f"  Background SLA ready ({card_count} pages): {sla_out}")
    return sla_out


def export_sla_to_pdf(
    sla_path: Path,
    scribus_cmd: str,
    script_dir: Path,
) -> "Path | None":
    """Export an SLA file to PDF via the export_to_pdf.py Scribus script."""
    pdf_path = sla_path.with_suffix(".pdf")
    env = os.environ.copy()
    env["SCRIBUS_PDF_OUTPUT"] = str(pdf_path)
    cmd = [scribus_cmd, str(sla_path), "-g", "-ns",
           "--python-script", str(script_dir / "export_to_pdf.py")]
    print(f"  {sla_path.name}  →  {pdf_path.name}")
    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.stdout.strip():
        print(result.stdout)
    if result.stderr.strip():
        print(f"  Scribus stderr: {result.stderr.strip()}")
    if result.returncode != 0:
        print(f"  ERROR: PDF export failed (exit {result.returncode})")
        return None
    if pdf_path.exists():
        print(f"  PDF created: {pdf_path}")
        return pdf_path
    print(f"  WARNING: PDF not found at expected path: {pdf_path}")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MaMo proxy print pipeline: download images then build Scribus SLA(s)."
    )
    parser.add_argument("xml_file", help="Path to the proxy XML file from MaMo.")
    parser.add_argument("--deck-name", "-d", default=None,
                        help="Override deck name used as image sub-folder and output folder.")
    parser.add_argument("--scribus", "-s", default=None,
                        help="Path to Scribus executable (overrides auto-detect).")
    parser.add_argument("--background", "-b", default=None,
                        help="Path to a background/cardback image. Generates a second SLA "
                             "with this image repeated once per card.")
    parser.add_argument("--pdf", action="store_true",
                        help="Export all produced SLA file(s) to PDF after building.")
    parser.add_argument("--create-cardback", action="store_true",
                        help="(legacy) Generate a cardback SLA from the XML <cardback> element.")
    parser.add_argument("--format", choices=["cardstock", "a4"], default="cardstock",
                        help="Output format: 'cardstock' (1 card/page Scribus SLA, default) or "
                             "'a4' (9 cards/page DIN A4 PDF via fpdf2).")
    parser.add_argument("--gap", choices=["0", "0.2", "3"], default="0.2",
                        help="[a4 only] Gap in mm between cards (default: 0.2).")
    parser.add_argument("--cut-marks", action="store_true",
                        help="[a4 only] Draw 3 mm cut marks at each card corner.")
    parser.add_argument("--watermark", action="store_true",
                        help="[a4 only] Add diagonal 'Playtest Card' text across each card.")
    parser.add_argument("--skip-basic-lands", action="store_true",
                        help="[a4 only] Omit basic land cards from the output.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    xml_path = Path(args.xml_file)
    if not xml_path.is_absolute():
        xml_path = Path.cwd() / xml_path

    # Derive a stable deck name by stripping the MaMo date+scope suffix
    # e.g. "MyDeck_2026-03-14_missing_proxy" -> "MyDeck"
    raw_stem = xml_path.stem
    if raw_stem.startswith("cards_"):
        raw_stem = raw_stem[6:]
    clean_stem = re.sub(r"_\d{4}-\d{2}-\d{2}_(missing|all)_proxy$", "", raw_stem)
    deck_name_resolved = args.deck_name or clean_stem
    print(f"Deck name: {deck_name_resolved}")

    # ── Step 1: Download card images ─────────────────────────────────────────
    print("=" * 60)
    print("STEP 1: Downloading card images from Scryfall")
    print("=" * 60)

    dl_cmd = [sys.executable, str(script_dir / "download_card_images.py"), str(xml_path),
              "--deck-name", deck_name_resolved]

    result = subprocess.run(dl_cmd)
    if result.returncode not in (0, 2):  # 2 = partial failure (some images missing)
        print(f"\nERROR: download_card_images.py failed (exit code {result.returncode})")
        return result.returncode
    if result.returncode == 2:
        print("\nWARNING: Some images failed to download. "
              "Continuing — missing images will appear as blank pages.")

    # ── A4 branch: generate 9-per-page PDF and exit ───────────────────────────
    if args.format == "a4":
        if args.background:
            print("\nWARNING: --background is ignored when --format a4 is used.")
        print()
        print("=" * 60)
        print("STEP 2: Generating DIN A4 PDF (9 cards/page)")
        print("=" * 60)
        a4_cmd = [sys.executable, str(script_dir / "generate_a4_pdf.py"), str(xml_path),
                  "--deck-name", deck_name_resolved]
        a4_cmd += ["--gap", args.gap]
        if args.cut_marks:
            a4_cmd.append("--cut-marks")
        if args.watermark:
            a4_cmd.append("--watermark")
        if args.skip_basic_lands:
            a4_cmd.append("--skip-basic-lands")
        a4_result = subprocess.run(a4_cmd)
        print()
        print("=" * 60)
        print("Done!")
        if a4_result.returncode == 0:
            a4_pdf = xml_path.parent / "ready2Print" / deck_name_resolved / f"{deck_name_resolved}_a4.pdf"
            if a4_pdf.exists():
                print(f"  PDF: {a4_pdf}")
        print("=" * 60)
        return a4_result.returncode

    # ── Step 2: Build front card SLA ──────────────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 2: Building front card SLA")
    print("=" * 60)

    scribus_cmd = args.scribus or find_scribus()
    if not scribus_cmd:
        print(
            "\nERROR: Scribus not found. Install Scribus or pass --scribus <path>.\n"
            "  Download: https://www.scribus.net/downloads/\n"
            "  Or set the SCRIBUS_CMD environment variable."
        )
        return 1

    print(f"Using Scribus: {scribus_cmd}\n")

    deck_name = deck_name_resolved

    xml_dir = xml_path.parent
    output_dir = xml_dir / "ready2Print" / deck_name

    env = os.environ.copy()
    env["SCRIBUS_CMD"] = scribus_cmd
    env["MTG_DIR"] = str(xml_dir / "mtg")

    sla_cmd = [sys.executable, str(script_dir / "simple_multi_page.py"), str(xml_path),
               "--output-dir", str(output_dir)]
    if args.create_cardback:
        sla_cmd.append("--create-cardback")

    result = subprocess.run(sla_cmd, env=env)
    if result.returncode != 0:
        print(f"\nERROR: simple_multi_page.py failed (exit code {result.returncode})")
        return result.returncode

    front_sla = output_dir / f"{deck_name}_multi.sla"
    sla_files: list[Path] = [front_sla] if front_sla.exists() else []

    # ── Step 3 (optional): Background SLA ────────────────────────────────────
    if args.background:
        print()
        print("=" * 60)
        print("STEP 3: Building background SLA")
        print("=" * 60)
        bg_image = Path(args.background)
        if not bg_image.exists():
            print(f"  ERROR: Background image not found: {bg_image}")
        else:
            bg_sla = build_background_sla(
                xml_path, bg_image, output_dir, deck_name, scribus_cmd, script_dir
            )
            if bg_sla:
                sla_files.append(bg_sla)

    # ── Step 4 (optional): Export to PDF ──────────────────────────────────────
    if args.pdf:
        print()
        print("=" * 60)
        print("STEP 4: Exporting to PDF")
        print("=" * 60)
        export_script = script_dir / "export_to_pdf.py"
        if not export_script.exists():
            print(f"  ERROR: {export_script} not found — cannot export PDFs.")
        else:
            for sla in sla_files:
                if sla.exists():
                    export_sla_to_pdf(sla, scribus_cmd, script_dir)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("Done!")
    for sla in sla_files:
        if sla.exists():
            print(f"  SLA: {sla}")
            pdf = sla.with_suffix(".pdf")
            if pdf.exists():
                print(f"  PDF: {pdf}")
    if not args.pdf:
        print("  → Open .sla file(s) in Scribus and export as PDF, or re-run with --pdf.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
