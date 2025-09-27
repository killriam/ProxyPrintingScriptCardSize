simple_multi_page.py — README

Overview

This document describes the `simple_multi_page.py` helper script. The script reads a deck XML file (cards.xml format used in this repo), copies a Scribus SLA template, duplicates the page for each front-card, and updates the image references in the SLA file so each page shows the correct card image. It can also optionally create a separate single-page cardback SLA that uses the deck's cardback image.

Location

- Script: `simple_multi_page.py` (this folder)
-- Template (default): `scribus_template_proxy.sla`
- Helper used to duplicate pages in Scribus: `copy_slaTemplate.py`
- Output directory (by default): `ready2Print/<deck_name>/`

Purpose

- Create a multi-page SLA where each page shows one card front image from the deck XML.
- Optionally create a single-page cardback SLA using the image referenced by the `<cardback>` tag in the XML (or common fallback names).

Requirements

- Python 3 (3.10+ recommended)
- Scribus available on PATH (or set `SCRIBUS_CMD` environment variable to the scribus executable)
- The project image files arranged under `mtg/images/<deck_name>/` (or `MTG_DIR` can point elsewhere)
- `copy_slaTemplate.py` present in the same directory and compatible with the installed Scribus version

Environment variables

- `SCRIBUS_CMD` (optional): path to the `scribus` executable. Default: `scribus`.
- `MTG_DIR` (optional): base `mtg/` directory. Default is `<base-dir>/mtg` (where base-dir is the script folder unless `--base-dir` is supplied).

How it works (high-level)

1. Parse the provided XML file and collect the `fronts/card` entries.
2. For each front card, find the matching image in the deck image folder. The image-finder is tolerant of appended Google Drive-like IDs (it will match filenames that start with the card name or contain the ID).
3. Copy the SLA template to `ready2Print/<deck_name>/<deck_name>_multi.sla`.
4. Call Scribus with `copy_slaTemplate.py` to duplicate page 1 for each additional card (one page exists by default in the template). This uses CLI-mode Scribus (headless script run).
5. After pages are present, update PFILE attributes in the SLA so each page's PAGEOBJECT points to the correct image path (relative to the output folder).
6. Optionally, when `--create-cardback` is set, create a single-page SLA for the cardback:
   - Find the `<cardback>` value in the XML and search the image folder for a file containing that ID (or try common fallback names like `cardback.png`).
   - Copy the same template (single page), sanitize it to make sure it contains exactly one `<PAGE .../>` element and `ANZPAGES="1"` (defensive), then update the PAGEOBJECT PFILE to point to the cardback image.

CLI / Usage

Examples (PowerShell):

Create multi-page front SLA and the single-page cardback SLA:

```powershell
python simple_multi_page.py 'Cards xml\Exilent Timing.xml' --create-cardback
```

Create only the multi-page front SLA (no cardback):

```powershell
python simple_multi_page.py 'Cards xml\Exilent Timing.xml'
```

Options

- `xml_file` (positional): Path to the deck XML file. If a relative path is given, it's relative to the script `--base-dir` (or the script folder by default).
-- `--template`, `-t`: SLA template path. Default: `scribus_template_proxy.sla`.
- `--output-dir`, `-o`: Custom name under `ready2Print/` to write output. Default: `ready2Print/<deck_name>/`.
- `--base-dir`, `-b`: Base directory for resolving relative paths (defaults to the script directory).
- `--create-cardback`: Also create a single-page cardback SLA next to the multi front SLA.

Cardback behavior and naming

- The cardback image is first searched for by using the XML `<cardback>` value (the script looks for files that include the cardback ID in the filename).
- If the ID-based search fails, the script tries common fallback names: `cardback.png`, `cardback.jpg`, `Cardback.png`, `Cardback.jpg`.
- The generated cardback SLA is written as `<deck_name>_cardback.sla` and will be a single-page document.

Notes and troubleshooting

- If Scribus fails to run or is not on PATH, set `SCRIBUS_CMD` to the executable path or install Scribus and ensure `scribus` is callable from the shell.
- If the script cannot find images, verify the deck folder under `mtg/images/<deck_name>/` and the exact filenames. The image lookup supports filenames that contain the card name plus an appended ID in parentheses (common in your repo).
- If your SLA template contains multiple PAGE elements already, the script now sanitizes the copied cardback SLA to keep only the first PAGE and sets `ANZPAGES="1"`.

Developer notes

- The script uses a regex-based replacement to update the `PFILE` attributes inside the SLA XML. This is robust for the current template structure but not a full Scribus XML parser—if you swap to a significantly different template, verify matches.
- `copy_slaTemplate.py` is used to duplicate the page inside Scribus; check that code for `COPIES` handling if you want different duplication behavior.

