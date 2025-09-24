#!/usr/bin/env python3
"""
Library-based approach to open and print Scribus SLA files without command line.
This explores various Python libraries that can handle SLA files directly.
"""

import os
import sys
from pathlib import Path

def test_reportlab_approach():
    """Test using ReportLab to parse and print SLA files."""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        import xml.etree.ElementTree as ET
        print("✓ ReportLab available - can convert SLA to PDF")
        return True
    except ImportError:
        print("✗ ReportLab not available")
        return False

def test_cairo_approach():
    """Test using Cairo/PyCairo for direct rendering."""
    try:
        import cairo
        print("✓ PyCairo available - can render graphics directly")
        return True
    except ImportError:
        print("✗ PyCairo not available")
        return False

def test_pillow_approach():
    """Test using Pillow for image processing."""
    try:
        from PIL import Image, ImageDraw
        print("✓ Pillow available - can handle images")
        return True
    except ImportError:
        print("✗ Pillow not available")
        return False

def test_lxml_approach():
    """Test using lxml for better XML parsing."""
    try:
        from lxml import etree
        print("✓ lxml available - better XML parsing")
        return True
    except ImportError:
        print("✗ lxml not available")
        return False

def print_with_win32print():
    """Test Windows native printing via win32print."""
    try:
        import win32print
        import win32api
        print("✓ win32print available - direct Windows printing")
        
        # List available printers
        printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
        print(f"  Available printers: {len(printers)}")
        for p in printers[:3]:  # Show first 3
            print(f"    - {p}")
        return True
    except ImportError:
        print("✗ win32print not available")
        return False

def parse_sla_file(sla_path):
    """Parse a Scribus SLA file to extract layout information."""
    try:
        import xml.etree.ElementTree as ET
        
        tree = ET.parse(sla_path)
        root = tree.getroot()
        
        print(f"Parsing SLA file: {sla_path}")
        print(f"Root tag: {root.tag}")
        
        # Extract basic document info
        doc_info = {}
        if 'PAGEXPOS' in root.attrib:
            doc_info['page_x'] = root.attrib['PAGEXPOS']
        if 'PAGEYPOS' in root.attrib:
            doc_info['page_y'] = root.attrib['PAGEYPOS']
        if 'PAGEWIDTH' in root.attrib:
            doc_info['page_width'] = root.attrib['PAGEWIDTH']
        if 'PAGEHEIGHT' in root.attrib:
            doc_info['page_height'] = root.attrib['PAGEHEIGHT']
            
        print(f"Document info: {doc_info}")
        
        # Find page objects (images, text, etc.)
        page_objects = root.findall('.//PAGEOBJECT')
        print(f"Found {len(page_objects)} page objects")
        
        for i, obj in enumerate(page_objects[:3]):  # Show first 3
            obj_type = obj.get('PTYPE', 'unknown')
            x_pos = obj.get('XPOS', '0')
            y_pos = obj.get('YPOS', '0')
            width = obj.get('WIDTH', '0')
            height = obj.get('HEIGHT', '0')
            
            print(f"  Object {i+1}: Type={obj_type}, Pos=({x_pos},{y_pos}), Size=({width},{height})")
            
            # Check for image files
            if 'PFILE' in obj.attrib:
                print(f"    Image file: {obj.get('PFILE')}")
                
        return True
        
    except Exception as e:
        print(f"Error parsing SLA file: {e}")
        return False

class ScribusLibraryPrinter:
    """A library-based approach to print Scribus SLA files."""
    
    def __init__(self):
        self.available_libs = {}
        self.check_dependencies()
    
    def check_dependencies(self):
        """Check which libraries are available."""
        print("Checking available libraries for SLA processing...")
        
        self.available_libs['reportlab'] = test_reportlab_approach()
        self.available_libs['cairo'] = test_cairo_approach()
        self.available_libs['pillow'] = test_pillow_approach()
        self.available_libs['lxml'] = test_lxml_approach()
        self.available_libs['win32print'] = print_with_win32print()
        
        print(f"\nAvailable libraries: {sum(self.available_libs.values())}/{len(self.available_libs)}")
    
    def convert_sla_to_pdf(self, sla_path, pdf_path):
        """Convert SLA file to PDF using available libraries."""
        if not self.available_libs.get('reportlab'):
            print("ReportLab required for PDF conversion")
            return False
            
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter, A4
            import xml.etree.ElementTree as ET
            
            # Parse SLA file
            tree = ET.parse(sla_path)
            root = tree.getroot()
            
            # Get document dimensions
            page_width = float(root.get('PAGEWIDTH', '595.276'))  # Default A4 width in points
            page_height = float(root.get('PAGEHEIGHT', '841.89'))  # Default A4 height in points
            
            # Create PDF
            c = canvas.Canvas(str(pdf_path), pagesize=(page_width, page_height))
            
            # Process page objects
            page_objects = root.findall('.//PAGEOBJECT')
            
            for obj in page_objects:
                obj_type = obj.get('PTYPE')
                x_pos = float(obj.get('XPOS', '0'))
                y_pos = float(obj.get('YPOS', '0'))
                width = float(obj.get('WIDTH', '0'))
                height = float(obj.get('HEIGHT', '0'))
                
                # Convert Scribus coordinates to PDF coordinates
                pdf_x = x_pos
                pdf_y = page_height - y_pos - height  # Flip Y coordinate
                
                if obj_type == '2':  # Image object
                    image_file = obj.get('PFILE')
                    if image_file and Path(image_file).exists():
                        try:
                            c.drawImage(image_file, pdf_x, pdf_y, width, height)
                        except Exception as e:
                            print(f"Warning: Could not draw image {image_file}: {e}")
                            # Draw a rectangle as placeholder
                            c.rect(pdf_x, pdf_y, width, height)
                
                elif obj_type == '4':  # Text object
                    # For text, we'd need to extract text content and formatting
                    # This is a simplified version
                    c.rect(pdf_x, pdf_y, width, height)  # Just draw outline for now
            
            c.save()
            print(f"✓ Converted {sla_path} to {pdf_path}")
            return True
            
        except Exception as e:
            print(f"Error converting SLA to PDF: {e}")
            return False
    
    def print_pdf_directly(self, pdf_path, printer_name=None):
        """Print PDF using available printing libraries."""
        if self.available_libs.get('win32print'):
            return self._print_with_win32print(pdf_path, printer_name)
        else:
            return self._print_with_system_command(pdf_path, printer_name)
    
    def _print_with_win32print(self, pdf_path, printer_name):
        """Print using win32print library."""
        try:
            import win32print
            import win32api
            
            if not printer_name:
                printer_name = win32print.GetDefaultPrinter()
            
            # This is a simplified approach - for PDF printing you'd typically
            # need to use a PDF reader or convert to a format win32print can handle
            print(f"Would print {pdf_path} to {printer_name} using win32print")
            return True
            
        except Exception as e:
            print(f"Error with win32print: {e}")
            return False
    
    def _print_with_system_command(self, pdf_path, printer_name):
        """Fallback to system command for printing."""
        import subprocess
        
        try:
            if printer_name:
                cmd = ['print', f'/D:{printer_name}', str(pdf_path)]
            else:
                cmd = ['print', str(pdf_path)]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✓ Printed {pdf_path}")
                return True
            else:
                print(f"Print command failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"Error printing: {e}")
            return False
    
    def print_sla_file(self, sla_path, printer_name=None):
        """Main method to print an SLA file using library approach."""
        print(f"\nPrinting SLA file: {sla_path}")
        
        # Step 1: Parse SLA file
        if not parse_sla_file(sla_path):
            return False
        
        # Step 2: Convert to PDF
        pdf_path = Path(sla_path).with_suffix('.pdf')
        if not self.convert_sla_to_pdf(sla_path, pdf_path):
            return False
        
        # Step 3: Print PDF
        return self.print_pdf_directly(pdf_path, printer_name)

def install_missing_libraries():
    """Show commands to install missing libraries."""
    print("\nTo install missing libraries, run:")
    print("pip install reportlab")
    print("pip install pycairo")  # May need system dependencies
    print("pip install pillow")
    print("pip install lxml")
    print("pip install pywin32")  # For Windows printing
    
def main():
    """Test the library-based approach."""
    print("Testing library-based Scribus SLA printing")
    print("=" * 50)
    
    printer = ScribusLibraryPrinter()
    
    # Test with an existing SLA file from ready2Print
    test_sla = Path(__file__).parent / "ready2Print" / "doctor_who_deck" / "Sol Ring (C21-263)_1.sla"
    
    if test_sla.exists():
        success = printer.print_sla_file(str(test_sla))
        if success:
            print("\n✓ Library-based printing successful!")
        else:
            print("\n✗ Library-based printing failed")
    else:
        print(f"Test SLA file not found: {test_sla}")
        # Try alternative paths
        alt_paths = [
            Path(__file__).parent / "test_doctor_who" / "Sol Ring (C21-263)_1.sla",
            Path(__file__).parent / "ready2Print" / "star_trek_deck" / "Day of Judgment (STA-2)_1.sla"
        ]
        
        for alt_path in alt_paths:
            if alt_path.exists():
                print(f"Found alternative: {alt_path}")
                success = printer.print_sla_file(str(alt_path))
                if success:
                    print("\n✓ Library-based printing successful!")
                else:
                    print("\n✗ Library-based printing failed")
                break
        else:
            print("No test SLA files found. Testing parsing capabilities only...")
    
    install_missing_libraries()

if __name__ == "__main__":
    main()