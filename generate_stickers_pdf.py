#!/usr/bin/env python3
"""
generate_stickers_pdf.py — Backward-compatibility alias for generate_markers_pdf.py.
"""
import sys
from generate_markers_pdf import main

if __name__ == "__main__":
    print("Notice: 'stickers' has been replaced by 'markers' (slip-in ID markers for card sleeves).")
    sys.exit(main())
