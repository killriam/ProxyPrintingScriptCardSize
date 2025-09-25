#!/usr/bin/env python3

import sys
sys.path.append('.')

from scribus_library_advanced import ScribusLibraryProcessor
from pathlib import Path
import PyPDF2

# Test the library processor
processor = ScribusLibraryProcessor()

# Use one of the existing SLA files
sla_path = Path("ready2Print/test_sla_layout_no_print/Black Lotus_0.sla")
pdf_path = sla_path.with_suffix('.pdf')

print(f"Testing SLA file: {sla_path}")
print(f"Output PDF: {pdf_path}")

if sla_path.exists():
    # Convert to PDF
    result = processor.convert_sla_to_pdf(str(sla_path), str(pdf_path))
    
    if result and pdf_path.exists():
        # Check PDF dimensions
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            page = pdf_reader.pages[0]
            
            # Get page dimensions
            mediabox = page.mediabox
            width_points = float(mediabox.width)
            height_points = float(mediabox.height)
            
            # Convert to inches
            width_inches = width_points / 72
            height_inches = height_points / 72
            
            print(f"\nPDF Dimensions:")
            print(f"  Width: {width_points:.1f} points ({width_inches:.2f} inches)")
            print(f"  Height: {height_points:.1f} points ({height_inches:.2f} inches)")
            
            # Check if it matches the expected SLA dimensions (252x252 points)
            if abs(width_points - 252) < 1 and abs(height_points - 252) < 1:
                print("✅ SUCCESS: PDF dimensions match SLA template (252x252 points)")
            else:
                print("❌ ISSUE: PDF dimensions don't match SLA template")
                print("  Expected: 252x252 points (3.5x3.5 inches)")
    else:
        print("❌ Failed to create PDF")
else:
    print(f"❌ SLA file not found: {sla_path}")