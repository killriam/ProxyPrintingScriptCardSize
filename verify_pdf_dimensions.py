#!/usr/bin/env python3
"""
Verify PDF dimensions to ensure they match the required 3.5" × 2.5" card layout.
"""

import os
from pathlib import Path

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from PyPDF2 import PdfReader
    PYPDF2_AVAILABLE = True
except ImportError:
    try:
        from pypdf import PdfReader
        PYPDF2_AVAILABLE = True
    except ImportError:
        PYPDF2_AVAILABLE = False

def check_pdf_dimensions(pdf_path):
    """Check the dimensions of a PDF file."""
    if not PYPDF2_AVAILABLE:
        print("PyPDF2 or pypdf required for PDF dimension checking")
        print("Install with: pip install PyPDF2")
        return None
    
    try:
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            page = reader.pages[0]  # First page
            
            # Get page dimensions in points
            width_points = float(page.mediabox.width)
            height_points = float(page.mediabox.height)
            
            # Convert to inches (72 points = 1 inch)
            width_inches = width_points / 72.0
            height_inches = height_points / 72.0
            
            return {
                'width_points': width_points,
                'height_points': height_points,
                'width_inches': width_inches,
                'height_inches': height_inches
            }
    except Exception as e:
        print(f"Error reading PDF {pdf_path}: {e}")
        return None

def verify_card_dimensions(pdf_path, expected_width=2.5, expected_height=3.5):
    """Verify that a PDF has the correct card dimensions."""
    dimensions = check_pdf_dimensions(pdf_path)
    if not dimensions:
        return False
    
    width_match = abs(dimensions['width_inches'] - expected_width) < 0.01
    height_match = abs(dimensions['height_inches'] - expected_height) < 0.01
    
    print(f"PDF: {Path(pdf_path).name}")
    print(f"  Dimensions: {dimensions['width_inches']:.2f}\" × {dimensions['height_inches']:.2f}\"")
    print(f"  Expected: {expected_width}\" × {expected_height}\"")
    print(f"  Width: {'✓' if width_match else '✗'} ({dimensions['width_inches']:.3f}\")")
    print(f"  Height: {'✓' if height_match else '✗'} ({dimensions['height_inches']:.3f}\")")
    
    return width_match and height_match

def main():
    """Check PDF dimensions in the ready2Print directories."""
    print("Verifying PDF card dimensions (expected: 3.5\" × 2.5\")")
    print("=" * 50)
    
    base_dir = Path(__file__).parent / "ready2Print"
    pdf_files = list(base_dir.glob("**/*.pdf"))
    
    if not pdf_files:
        print("No PDF files found in ready2Print directories")
        return
    
    if not PYPDF2_AVAILABLE:
        print("Installing PyPDF2 for PDF dimension checking...")
        try:
            import subprocess
            subprocess.run(["pip", "install", "PyPDF2"], check=True)
            from PyPDF2 import PdfReader
            print("PyPDF2 installed successfully")
        except Exception as e:
            print(f"Could not install PyPDF2: {e}. Skipping dimension verification.")
            return
    
    correct_count = 0
    total_count = 0
    
    for pdf_file in pdf_files[:5]:  # Check first 5 PDFs
        print()
        if verify_card_dimensions(str(pdf_file)):
            correct_count += 1
        total_count += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {correct_count}/{total_count} PDFs have correct dimensions")
    
    if correct_count == total_count:
        print("✓ All checked PDFs have the correct card dimensions!")
    else:
        print("✗ Some PDFs do not match the expected dimensions")

if __name__ == "__main__":
    main()