#!/usr/bin/env python3
"""
Test script for Scribus printer configuration and direct printing.
This script helps test and configure native Scribus printing capabilities.
"""

import os
import sys
import subprocess
import tempfile
from pathlib import Path

def test_scribus_printer_config():
    """Test Scribus printer configuration and list available printers."""
    
    scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
    
    # Create test script to list printers
    script_content = '''
import scribus
import sys

try:
    # Get available printers
    printers = scribus.getPrinterNames()
    
    print(f"Available printers ({len(printers)}):", file=sys.stderr)
    for i, printer in enumerate(printers, 1):
        print(f"  {i}. {printer}", file=sys.stderr)
    
    # Get current default printer
    if printers:
        current_printer = scribus.getPrinter()
        print(f"Current printer: {current_printer}", file=sys.stderr)
    
    print("Printer configuration test completed successfully!", file=sys.stderr)
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(script_content)
        script_path = f.name
    
    try:
        print("Testing Scribus printer configuration...")
        print(f"Using Scribus: {scribus_cmd}")
        
        # Run Scribus with the test script
        cmd = [scribus_cmd, "-g", "-ns", "-py", script_path]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        print("\n--- Scribus Output ---")
        if result.stdout:
            print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"Return code: {result.returncode}")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("ERROR: Scribus test timed out")
        return False
    except FileNotFoundError:
        print(f"ERROR: Scribus executable not found: {scribus_cmd}")
        print("Please set SCRIBUS_CMD environment variable or add Scribus to PATH")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        try:
            os.unlink(script_path)
        except:
            pass

def test_print_single_file(sla_file, printer_name):
    """Test printing a single SLA file to specified printer."""
    
    if not Path(sla_file).exists():
        print(f"ERROR: File not found: {sla_file}")
        return False
    
    scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
    
    # Create print script
    script_content = f'''
import scribus
import sys
import traceback

try:
    if not scribus.haveDoc():
        print("ERROR: No document loaded", file=sys.stderr)
        sys.exit(1)

    # Get available printers
    printers = scribus.getPrinterNames()
    print(f"Available printers: {{printers}}", file=sys.stderr)
    
    # Check if target printer exists
    target_printer = "{printer_name}"
    if target_printer not in printers:
        print(f"ERROR: Printer '{{target_printer}}' not found!", file=sys.stderr)
        print(f"Available printers: {{printers}}", file=sys.stderr)
        sys.exit(1)

    # Set the printer
    scribus.setPrinter(target_printer)
    print(f"Printer set to: {{target_printer}}", file=sys.stderr)
    
    # Set print options (1 copy, from page 1 to 1, color mode)
    scribus.setPrintOptions(1, 1, 1, 0, 0, 1)
    
    # Print the document
    scribus.printDocument()
    print(f"SUCCESS: Document sent to printer {{target_printer}}", file=sys.stderr)

except Exception as e:
    print(f"ERROR during printing: {{e}}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(script_content)
        script_path = f.name
    
    try:
        print(f"Testing print of {sla_file} to printer '{printer_name}'...")
        
        # Run Scribus with the print script
        cmd = [scribus_cmd, "-g", "-ns", "-py", script_path, str(sla_file)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        print("\n--- Print Result ---")
        if result.stdout:
            print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"Return code: {result.returncode}")
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        try:
            os.unlink(script_path)
        except:
            pass

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test Scribus printer configuration")
    parser.add_argument("--test-config", action="store_true", help="Test printer configuration")
    parser.add_argument("--print-file", help="Test print a specific SLA file")
    parser.add_argument("--printer", help="Printer name for test printing")
    
    args = parser.parse_args()
    
    if args.test_config:
        success = test_scribus_printer_config()
        sys.exit(0 if success else 1)
    
    if args.print_file:
        if not args.printer:
            print("ERROR: --printer required when using --print-file")
            sys.exit(1)
        success = test_print_single_file(args.print_file, args.printer)
        sys.exit(0 if success else 1)
    
    # Default: run configuration test
    success = test_scribus_printer_config()
    sys.exit(0 if success else 1)