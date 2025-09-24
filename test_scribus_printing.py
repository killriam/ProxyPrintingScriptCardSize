#!/usr/bin/env python3
"""
Simple test to prove automatic printing via Scribus command line works.
This script uses an existing SLA file and attempts to print it using Scribus in headless mode.
"""

import os
import subprocess
import sys
from pathlib import Path

def create_print_script():
    """Create a temporary Python script for Scribus to execute printing."""
    script_content = '''
import scribus
import sys
import traceback

try:
    if not scribus.haveDoc():
        print("ERROR: No document loaded", file=sys.stderr)
        sys.exit(1)

    # Get available printers
    printers = scribus.getPrinterNames()
    if not printers:
        print("ERROR: No printers available", file=sys.stderr)
        sys.exit(1)

    # Use the first available printer
    printer = printers[0]
    print(f"Using printer: {printer}", file=sys.stderr)

    # Set the printer
    scribus.setPrinter(printer)

    # Print the document
    scribus.printDocument()
    print("Print command executed successfully", file=sys.stderr)

except Exception as e:
    print(f"ERROR during printing: {e}", file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
'''
    return script_content

def test_scribus_printing(sla_file_path):
    """Test printing a Scribus file via command line."""
    print(f"Testing Scribus command line printing with file: {sla_file_path}")

    # Check if SLA file exists
    if not Path(sla_file_path).exists():
        print(f"ERROR: SLA file not found: {sla_file_path}")
        return False

    # Create temporary print script
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(create_print_script())
        script_path = f.name

    try:
        # Build Scribus command
        scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
        cmd = [
            scribus_cmd,
            "-g",  # No GUI
            "-ns", # No splash screen
            "-py", script_path,  # Python script to run
            sla_file_path
        ]

        print(f"Running command: {' '.join(cmd)}")

        # Run the command
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        print("Return code:", result.returncode)
        if result.stdout:
            print("STDOUT:", result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        # Check for success
        if result.returncode == 0:
            print("SUCCESS: Scribus command completed without error.")
            print("This proves that automatic printing via Scribus command line can work.")
            return True
        else:
            print("FAILURE: Scribus command failed.")
            return False

    except subprocess.TimeoutExpired:
        print("ERROR: Command timed out")
        return False
    except FileNotFoundError:
        print("ERROR: Scribus executable not found. Make sure Scribus is installed and in PATH.")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False
    finally:
        # Clean up temporary script
        try:
            os.unlink(script_path)
        except:
            pass

def main():
    # Use one of the test SLA files
    test_sla = Path(__file__).parent / "test_doctor_who" / "Sol Ring (C21-263)_1.sla"

    if not test_sla.exists():
        print(f"Test SLA file not found: {test_sla}")
        print("Please ensure test files exist.")
        sys.exit(1)

    success = test_scribus_printing(str(test_sla))

    if success:
        print("\n✓ Test passed: Automatic printing via Scribus command line works!")
    else:
        print("\n✗ Test failed: Automatic printing did not work.")
        sys.exit(1)

if __name__ == "__main__":
    main()