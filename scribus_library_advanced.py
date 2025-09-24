#!/usr/bin/env python3
"""
Advanced library-based Scribus SLA printer with full printing support.
This replaces command-line Scribus calls with pure Python libraries.
"""

import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import mm, inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    import win32print
    import win32api
    WIN32PRINT_AVAILABLE = True
except ImportError:
    WIN32PRINT_AVAILABLE = False

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

class ScribusLibraryProcessor:
    """Pure Python library for processing and printing Scribus SLA files."""
    
    def __init__(self):
        self.check_dependencies()
    
    def check_dependencies(self):
        """Check required libraries."""
        missing = []
        if not REPORTLAB_AVAILABLE:
            missing.append("reportlab")
        if not WIN32PRINT_AVAILABLE:
            missing.append("pywin32")
        if not PILLOW_AVAILABLE:
            missing.append("pillow")
            
        if missing:
            print(f"Missing libraries: {', '.join(missing)}")
            print(f"Install with: pip install {' '.join(missing)}")
            return False
        return True
    
    def get_available_printers(self):
        """Get list of available Windows printers."""
        if not WIN32PRINT_AVAILABLE:
            return []
        
        try:
            printers = [printer[2] for printer in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL)]
            return printers
        except Exception:
            return []
    
    def parse_sla_file(self, sla_path):
        """Parse Scribus SLA file and extract layout information."""
        try:
            tree = ET.parse(sla_path)
            root = tree.getroot()
            
            # Extract document properties
            doc_info = {
                'page_width': float(root.get('PAGEWIDTH', '595.276')),  # A4 width in points
                'page_height': float(root.get('PAGEHEIGHT', '841.89')), # A4 height in points
                'page_x': float(root.get('PAGEXPOS', '0')),
                'page_y': float(root.get('PAGEYPOS', '0')),
            }
            
            # Extract page objects
            page_objects = []
            for obj in root.findall('.//PAGEOBJECT'):
                obj_info = {
                    'type': obj.get('PTYPE', '0'),
                    'x': float(obj.get('XPOS', '0')),
                    'y': float(obj.get('YPOS', '0')),
                    'width': float(obj.get('WIDTH', '0')),
                    'height': float(obj.get('HEIGHT', '0')),
                    'image_file': obj.get('PFILE', ''),
                    'rotation': float(obj.get('ROT', '0')),
                }
                page_objects.append(obj_info)
            
            return {
                'document': doc_info,
                'objects': page_objects
            }
            
        except Exception as e:
            print(f"Error parsing SLA file: {e}")
            return None
    
    def convert_sla_to_pdf(self, sla_path, pdf_path=None):
        """Convert SLA file to PDF using ReportLab with standard card dimensions.
        
        Generates PDFs with standard trading card dimensions:
        - Width: 2.5 inches (180 points)
        - Height: 3.5 inches (252 points)
        
        The content is scaled proportionally to fit within these dimensions
        while maintaining aspect ratio.
        """
        if not REPORTLAB_AVAILABLE:
            print("ReportLab required for PDF conversion")
            return None
        
        if pdf_path is None:
            pdf_path = Path(sla_path).with_suffix('.pdf')
        
        # Parse SLA file
        sla_data = self.parse_sla_file(sla_path)
        if not sla_data:
            return None
        
        doc_info = sla_data['document']
        page_objects = sla_data['objects']
        
        try:
            # Use standard card dimensions: 3.5" height × 2.5" width
            # Convert inches to points (1 inch = 72 points)
            CARD_WIDTH_POINTS = 2.5 * 72   # 180 points
            CARD_HEIGHT_POINTS = 3.5 * 72  # 252 points
            
            # Create PDF canvas with card dimensions
            c = canvas.Canvas(
                str(pdf_path), 
                pagesize=(CARD_WIDTH_POINTS, CARD_HEIGHT_POINTS)
            )
            
            # Use card dimensions instead of original document dimensions
            card_doc_info = {
                'page_width': CARD_WIDTH_POINTS,
                'page_height': CARD_HEIGHT_POINTS,
                'page_x': 0,
                'page_y': 0
            }
            
            # Process each object with scaling to fit card dimensions
            for obj in page_objects:
                self._draw_object_to_pdf(c, obj, card_doc_info, sla_path, doc_info)
            
            # Save PDF
            c.save()
            print(f"✓ Converted SLA to PDF: {pdf_path}")
            return pdf_path
            
        except Exception as e:
            print(f"Error creating PDF: {e}")
            return None
    
    def _draw_object_to_pdf(self, canvas_obj, obj_info, card_doc_info, sla_path, original_doc_info=None):
        """Draw a single object to the PDF canvas with scaling to fit card dimensions."""
        obj_type = obj_info['type']
        
        # Calculate scaling factors if original document info is provided
        if original_doc_info:
            scale_x = card_doc_info['page_width'] / original_doc_info['page_width']
            scale_y = card_doc_info['page_height'] / original_doc_info['page_height']
            
            # Use the same scale for both dimensions to maintain aspect ratio
            scale = min(scale_x, scale_y)
            
            # Scale and center the object
            scaled_width = obj_info['width'] * scale
            scaled_height = obj_info['height'] * scale
            scaled_x = (obj_info['x'] * scale) + (card_doc_info['page_width'] - original_doc_info['page_width'] * scale) / 2
            scaled_y = (obj_info['y'] * scale) + (card_doc_info['page_height'] - original_doc_info['page_height'] * scale) / 2
        else:
            # No scaling, use original dimensions
            scaled_x = obj_info['x']
            scaled_y = obj_info['y']
            scaled_width = obj_info['width']
            scaled_height = obj_info['height']
        
        # Convert Y coordinate (PDF coordinate system has origin at bottom-left)
        y = card_doc_info['page_height'] - scaled_y - scaled_height
        x = scaled_x
        width = scaled_width
        height = scaled_height
        
        if obj_type == '2':  # Image object
            image_file = obj_info['image_file']
            if image_file:
                # Handle relative paths
                if not os.path.isabs(image_file):
                    image_file = os.path.join(os.path.dirname(sla_path), image_file)
                
                # Normalize path
                image_file = os.path.normpath(image_file)
                
                if os.path.exists(image_file):
                    try:
                        canvas_obj.drawImage(image_file, x, y, width, height)
                        return
                    except Exception as e:
                        print(f"Warning: Could not draw image {image_file}: {e}")
                
                # Draw placeholder rectangle if image failed
                canvas_obj.setStrokeColor('red')
                canvas_obj.setFillColor('lightgray')
                canvas_obj.rect(x, y, width, height, fill=1)
                canvas_obj.setFillColor('red')
                canvas_obj.drawCentredString(x + width/2, y + height/2, "IMAGE")
        
        elif obj_type == '4':  # Text object
            # Draw text placeholder
            canvas_obj.setStrokeColor('blue')
            canvas_obj.rect(x, y, width, height)
            canvas_obj.setFillColor('blue')
            canvas_obj.drawCentredString(x + width/2, y + height/2, "TEXT")
        
        else:
            # Draw generic object
            canvas_obj.setStrokeColor('gray')
            canvas_obj.rect(x, y, width, height)
    
    def print_pdf_file(self, pdf_path, printer_name=None, copies=1):
        """Print PDF file using Windows printing."""
        if not WIN32PRINT_AVAILABLE:
            return self._fallback_print(pdf_path, printer_name)
        
        try:
            if not printer_name:
                printer_name = win32print.GetDefaultPrinter()
            
            # For actual PDF printing with win32print, you'd need to:
            # 1. Convert PDF to raw printer format, or
            # 2. Use a PDF reader like Acrobat Reader via COM, or  
            # 3. Use system print command
            
            # For now, use system command as it's most reliable
            return self._fallback_print(pdf_path, printer_name)
            
        except Exception as e:
            print(f"win32print error: {e}")
            return self._fallback_print(pdf_path, printer_name)
    
    def _fallback_print(self, pdf_path, printer_name):
        """Fallback printing using system commands."""
        import subprocess
        
        methods = [
            # Method 1: Direct print command
            lambda: subprocess.run(['print', f'/D:{printer_name}' if printer_name else '', str(pdf_path)], 
                                 capture_output=True, text=True, timeout=30),
            
            # Method 2: SumatraPDF (if available)
            lambda: subprocess.run(['SumatraPDF.exe', '-print-to', printer_name or 'default', str(pdf_path)], 
                                 capture_output=True, text=True, timeout=30),
            
            # Method 3: Adobe Acrobat Reader (if available)
            lambda: subprocess.run(['AcroRd32.exe', '/t', str(pdf_path), printer_name or 'default'], 
                                 capture_output=True, text=True, timeout=30),
            
            # Method 4: PowerShell
            lambda: subprocess.run(['powershell', '-Command', 
                                  f'Start-Process -FilePath "{pdf_path}" -Verb Print'], 
                                 capture_output=True, text=True, timeout=30),
        ]
        
        for i, method in enumerate(methods, 1):
            try:
                result = method()
                if result.returncode == 0:
                    print(f"✓ Printed via method {i}")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
            except Exception:
                continue
        
        print("✗ All print methods failed")
        return False
    
    def print_sla_file(self, sla_path, printer_name=None, copies=1):
        """Main method: convert SLA to PDF and print."""
        print(f"Processing SLA file: {sla_path}")
        
        # Convert to PDF
        pdf_path = self.convert_sla_to_pdf(sla_path)
        if not pdf_path:
            return False
        
        # Print PDF
        success = True
        for copy_num in range(copies):
            copy_suffix = f" (copy {copy_num + 1})" if copies > 1 else ""
            print(f"Printing{copy_suffix}...")
            
            if not self.print_pdf_file(pdf_path, printer_name):
                success = False
        
        return success
    
    def print_sla_files_batch(self, sla_files, printer_name=None, copies=1):
        """Print multiple SLA files."""
        if not self.check_dependencies():
            return False
        
        print(f"Processing {len(sla_files)} SLA files...")
        if printer_name:
            print(f"Target printer: {printer_name}")
        else:
            print("Using default printer")
        
        failures = 0
        for i, sla_file in enumerate(sla_files, 1):
            print(f"\n[{i}/{len(sla_files)}] {Path(sla_file).name}")
            
            if not self.print_sla_file(sla_file, printer_name, copies):
                failures += 1
        
        if failures == 0:
            print(f"\n✓ All {len(sla_files)} files processed successfully!")
        else:
            print(f"\n✗ {failures}/{len(sla_files)} files failed")
        
        return failures == 0

def main():
    """Test the library processor."""
    processor = ScribusLibraryProcessor()
    
    # Test with available SLA files
    test_files = []
    base_path = Path(__file__).parent
    
    # Look for SLA files
    for pattern in ["ready2Print/**/*.sla", "test_*/**/*.sla"]:
        test_files.extend(base_path.glob(pattern))
    
    if not test_files:
        print("No SLA files found for testing")
        return
    
    # Test with first file
    test_file = test_files[0]
    print(f"Testing with: {test_file}")
    
    success = processor.print_sla_file(str(test_file))
    if success:
        print("✓ Library-based SLA processing works!")
    else:
        print("✗ Library-based SLA processing failed")

if __name__ == "__main__":
    main()