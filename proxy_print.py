#!/usr/bin/env python3
"""
proxy_print.py — MaMo one-command proxy print pipeline

Runs both steps in sequence:
  1. download_card_images.py  — fetch card images from Scryfall
  2. simple_multi_page.py     — build multi-page Scribus SLA

Usage:
    python proxy_print.py <xml_file> [--deck-name <name>] [--scribus <path>] [--create-cardback]

Arguments:
    xml_file                Path to the proxy XML exported from MaMo DeckFinishingStep.
    --deck-name, -d         Override deck name (default: derived from XML filename).
    --scribus, -s           Path to Scribus executable (default: auto-detect or SCRIBUS_CMD env var).
    --create-cardback       Also generate a cardback SLA (passed through to simple_multi_page.py).

Examples:
    python proxy_print.py my_deck_missing_proxy.xml
    python proxy_print.py my_deck_missing_proxy.xml --deck-name "MyDeck"
    python proxy_print.py my_deck_missing_proxy.xml --scribus "C:\\Program Files\\Scribus 1.6.5\\Scribus.exe"
"""

import argparse
import os
import sys
import subprocess
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
    # Respect explicit env var first
    env_cmd = os.environ.get("SCRIBUS_CMD")
    if env_cmd:
        return env_cmd
    for candidate in SCRIBUS_CANDIDATES:
        p = Path(candidate)
        if p.is_absolute():
            if p.exists():
                return str(p)
        else:
            # Try as a PATH command
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MaMo proxy print pipeline: download images then build Scribus SLA."
    )
    parser.add_argument("xml_file", help="Path to the proxy XML file from MaMo.")
    parser.add_argument("--deck-name", "-d", default=None,
                        help="Override deck name used as image sub-folder and output folder.")
    parser.add_argument("--scribus", "-s", default=None,
                        help="Path to Scribus executable (overrides auto-detect).")
    parser.add_argument("--create-cardback", action="store_true",
                        help="Also create a single-page cardback SLA.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    xml_path = Path(args.xml_file)

    # ── Step 1: Download card images ─────────────────────────────────────────
    print("=" * 60)
    print("STEP 1: Downloading card images from Scryfall")
    print("=" * 60)

    dl_cmd = [sys.executable, str(script_dir / "download_card_images.py"), str(xml_path)]
    if args.deck_name:
        dl_cmd += ["--deck-name", args.deck_name]

    result = subprocess.run(dl_cmd)
    if result.returncode not in (0, 2):  # 2 = partial failure (some images missing)
        print(f"\nERROR: download_card_images.py failed (exit code {result.returncode})")
        return result.returncode
    if result.returncode == 2:
        print("\nWARNING: Some images failed to download. Continuing anyway — missing images will be blank pages.")

    # ── Step 2: Build Scribus SLA ─────────────────────────────────────────────
    print()
    print("=" * 60)
    print("STEP 2: Building Scribus SLA")
    print("=" * 60)

    # Resolve Scribus path
    scribus_cmd = args.scribus or find_scribus()
    if not scribus_cmd:
        print(
            "\nERROR: Scribus not found. Install Scribus or pass --scribus <path>.\n"
            "  Download: https://www.scribus.net/downloads/\n"
            "  Or set the SCRIBUS_CMD environment variable."
        )
        return 1

    print(f"Using Scribus: {scribus_cmd}\n")

    env = os.environ.copy()
    env["SCRIBUS_CMD"] = scribus_cmd

    sla_cmd = [sys.executable, str(script_dir / "simple_multi_page.py"), str(xml_path),
               "--base-dir", str(xml_path.parent)]
    if args.deck_name:
        sla_cmd += ["--output-dir", args.deck_name]
    if args.create_cardback:
        sla_cmd.append("--create-cardback")

    result = subprocess.run(sla_cmd, env=env)
    if result.returncode != 0:
        print(f"\nERROR: simple_multi_page.py failed (exit code {result.returncode})")
        return result.returncode

    print()
    print("=" * 60)
    print("Done! Open the .sla file in Scribus and export as PDF.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
