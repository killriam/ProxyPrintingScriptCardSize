#!/usr/bin/env python3
"""
export_to_pdf.py — Scribus Python script: export the current document to PDF.

Intended to be run by proxy_print.py via Scribus in headless mode:
    scribus <document.sla> -g -ns --python-script export_to_pdf.py

The output PDF path is taken from the SCRIBUS_PDF_OUTPUT environment variable.
If not set, it defaults to the same path as the SLA file with a .pdf extension.
"""

import scribus
import os
import sys

if not scribus.haveDoc():
    print("export_to_pdf.py: No document is open.", file=sys.stderr)
    sys.exit(1)

doc_path = scribus.getDocName()
pdf_path = os.environ.get("SCRIBUS_PDF_OUTPUT",
                          os.path.splitext(doc_path)[0] + ".pdf")

print(f"export_to_pdf.py: Exporting '{doc_path}' -> '{pdf_path}'")

pdf = scribus.PDF()
pdf.file = pdf_path
pdf.save()

print("export_to_pdf.py: Export complete.")
scribus.closeDoc()
