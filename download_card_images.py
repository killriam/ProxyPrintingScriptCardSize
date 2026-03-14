#!/usr/bin/env python3
"""
download_card_images.py — MaMo companion script for proxy printing

Reads a proxy XML file (cards.xml format from MaMo's "Print Proxies" export),
downloads card images from the Scryfall API, and saves them to the image
directory expected by simple_multi_page.py.

Usage:
    python download_card_images.py <xml_file> [--deck-name <name>] [--out-dir <dir>]

Arguments:
    xml_file            Path to the proxy XML file (exported from MaMo DeckFinishingStep).
    --deck-name, -d     Override deck name (default: XML filename stem, strips "cards_" prefix).
    --out-dir, -o       Override output base directory (default: mtg/images/ next to this script).

Example:
    python download_card_images.py "My_Deck_missing_proxy.xml"
    python download_card_images.py "My_Deck_missing_proxy.xml" --deck-name "MyDeck"

Notes:
    - Images are saved to: <xml_dir>/mtg/images/<deck_name>/<CardName>_normal.jpg
    - Scryfall rate limit is ~10 req/s; this script waits 110 ms between requests.
    - Already-downloaded images are skipped automatically.
"""

import argparse
import os
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
import json
import xml.etree.ElementTree as ET
from pathlib import Path

SCRYFALL_NAMED_URL = "https://api.scryfall.com/cards/named"
REQUEST_DELAY_S = 0.11  # 110 ms — stay safely under Scryfall's 10 req/s limit
HEADERS = {
    "User-Agent": "MaMo-ProxyPrinting/1.0 (https://github.com/killriam/MaMo)",
    "Accept": "application/json",
}


def sanitize_filename(name: str) -> str:
    """Replace filesystem-unsafe characters with underscores."""
    for ch in r'/\:*?"<>|':
        name = name.replace(ch, "_")
    return name


def scryfall_get(url: str) -> dict | None:
    """Perform an HTTP GET against a Scryfall endpoint and return parsed JSON, or None on error."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code} for {url}: {e.reason}")
        return None
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None


def download_file(url: str, dest_path: Path) -> bool:
    """Download a binary file from *url* to *dest_path*. Returns True on success."""
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(resp.read())
        return True
    except Exception as e:
        print(f"  Download error for {url}: {e}")
        return False


def collect_card_names_from_xml(xml_path: Path) -> list[str]:
    """
    Parse the proxy XML and return a list of card names (with copies expanded).

    The XML format produced by MaMo DeckFinishingStep is:
        <cardpacks>
          <fronts>
            <card><name>{CardName}_normal.jpg</name></card>
            ...
          </fronts>
        </cardpacks>

    Each <card> entry represents one physical copy needed, so a card that appears
    three times in this list requires three pages in the SLA.
    """
    tree = ET.parse(str(xml_path))
    root = tree.getroot()

    fronts = root.find("fronts")
    if fronts is None:
        raise ValueError("No <fronts> element found in XML — is this a MaMo proxy XML?")

    names: list[str] = []
    for card_elem in fronts.findall("card"):
        name_elem = card_elem.find("name")
        if name_elem is None or not name_elem.text:
            print("  Warning: <card> element without <name>, skipping.")
            continue
        names.append(name_elem.text.strip())

    return names


def strip_image_suffix(raw_name: str) -> str:
    """
    Convert the image filename stored in XML to a Scryfall card name.
    E.g. "Lightning Bolt_normal.jpg"  -> "Lightning Bolt"
         "Arid Mesa_large.jpg"        -> "Arid Mesa"
    """
    name = raw_name
    for suffix in ("_normal.jpg", "_normal.png", "_large.jpg", "_large.png",
                   "_small.jpg", "_small.png", ".jpg", ".png"):
        if name.lower().endswith(suffix.lower()):
            name = name[: -len(suffix)]
            break
    return name.strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download card images for MaMo proxy printing from Scryfall."
    )
    parser.add_argument("xml_file", help="Path to the proxy XML file.")
    parser.add_argument(
        "--deck-name", "-d",
        default=None,
        help="Override deck name used as the image sub-folder (default: XML stem).",
    )
    parser.add_argument(
        "--out-dir", "-o",
        default=None,
        help="Base image directory (default: <xml_dir>/mtg/images).",
    )
    args = parser.parse_args()

    xml_path = Path(args.xml_file)
    if not xml_path.is_absolute():
        xml_path = Path.cwd() / xml_path
    if not xml_path.exists():
        print(f"Error: XML file not found: {xml_path}")
        return 1

    # Determine deck name from XML filename (mirrors simple_multi_page.py logic).
    # Strip the MaMo date+scope suffix so images are reused across re-exports:
    # e.g. "MyDeck_2026-03-14_missing_proxy" -> "MyDeck"
    import re as _re
    raw_stem = args.deck_name or xml_path.stem
    if raw_stem.startswith("cards_"):
        raw_stem = raw_stem[6:]
    deck_name = _re.sub(r"_\d{4}-\d{2}-\d{2}_(missing|all)_proxy$", "", raw_stem)

    base_image_dir = Path(args.out_dir) if args.out_dir else xml_path.parent / "mtg" / "images"
    output_dir = base_image_dir / deck_name
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Saving images to: {output_dir}")

    # Parse XML
    try:
        raw_names = collect_card_names_from_xml(xml_path)
    except (ET.ParseError, ValueError) as exc:
        print(f"Error parsing XML: {exc}")
        return 1

    if not raw_names:
        print("No card entries found in XML.")
        return 0

    print(f"Found {len(raw_names)} card entries in XML.")

    # Deduplicate for API calls (we download each unique image once)
    unique_names: list[str] = []
    seen: set[str] = set()
    for raw in raw_names:
        card_name = strip_image_suffix(raw)
        if card_name not in seen:
            seen.add(card_name)
            unique_names.append(card_name)

    print(f"{len(unique_names)} unique cards to download.\n")

    ok_count = 0
    skip_count = 0
    fail_count = 0

    for i, card_name in enumerate(unique_names):
        # Expected destination filename (same convention MaMo uses for GCS)
        safe_name = sanitize_filename(card_name)
        dest_filename = f"{safe_name}_normal.jpg"
        dest_path = output_dir / dest_filename

        if dest_path.exists():
            print(f"[{i+1}/{len(unique_names)}] Skipping (already exists): {card_name}")
            skip_count += 1
            continue

        print(f"[{i+1}/{len(unique_names)}] Fetching: {card_name}")

        # Step 1: look up card metadata from Scryfall
        encoded_name = urllib.parse.quote(card_name)
        api_url = f"{SCRYFALL_NAMED_URL}?exact={encoded_name}&format=json"
        data = scryfall_get(api_url)
        time.sleep(REQUEST_DELAY_S)

        if data is None:
            # Try fuzzy search as fallback
            print(f"  Exact match failed, trying fuzzy…")
            api_url = f"{SCRYFALL_NAMED_URL}?fuzzy={encoded_name}&format=json"
            data = scryfall_get(api_url)
            time.sleep(REQUEST_DELAY_S)

        if data is None or data.get("object") == "error":
            print(f"  Could not find card on Scryfall: {card_name}")
            fail_count += 1
            continue

        # Step 2: resolve the image URL (normal > large > png > small)
        image_url: str | None = None
        image_uris = data.get("image_uris", {})
        if not image_uris:
            # Double-faced cards store faces in card_faces
            faces = data.get("card_faces", [])
            if faces:
                image_uris = faces[0].get("image_uris", {})

        for quality in ("normal", "large", "png", "small"):
            if quality in image_uris:
                image_url = image_uris[quality]
                break

        if not image_url:
            print(f"  No image_uris found for: {card_name}")
            fail_count += 1
            continue

        # Step 3: download the image
        if download_file(image_url, dest_path):
            print(f"  Saved: {dest_path.name}")
            ok_count += 1
        else:
            fail_count += 1

    print(f"\nDone. Downloaded: {ok_count} | Skipped: {skip_count} | Failed: {fail_count}")
    if fail_count > 0:
        print("Re-run the script to retry failed downloads.")
        return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
