#!/usr/bin/env python3
"""
Scribus Native Printing Setup and Usage Guide
This script helps set up and use native Scribus printing for Magic card printing.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_scribus_installation():
    """Check if Scribus is properly installed and accessible."""
    print("=== Scribus Installation Check ===")
    
    scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
    print(f"Checking Scribus command: {scribus_cmd}")
    
    try:
        result = subprocess.run([scribus_cmd, "--version"], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"✓ Scribus found: {version}")
            return True
        else:
            print(f"✗ Scribus command failed with return code {result.returncode}")
            if result.stderr:
                print(f"  Error: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print(f"✗ Scribus executable not found: {scribus_cmd}")
        print("  Please install Scribus or set SCRIBUS_CMD environment variable")
        return False
    except subprocess.TimeoutExpired:
        print(f"✗ Scribus command timed out")
        return False
    except Exception as e:
        print(f"✗ Error checking Scribus: {e}")
        return False

def list_available_printers():
    """List available system printers."""
    print("\n=== Available System Printers ===")
    
    try:
        # Try PowerShell method
        result = subprocess.run([
            "powershell", "-Command", 
            "Get-Printer | Select-Object Name, PrinterStatus | Format-Table -AutoSize"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and result.stdout.strip():
            print("System printers (via PowerShell):")
            print(result.stdout)
            return True
        else:
            print("PowerShell printer query failed, trying WMI...")
            
    except Exception as e:
        print(f"PowerShell method failed: {e}")
    
    try:
        # Try WMIC method as fallback
        result = subprocess.run([
            "wmic", "printer", "get", "name,status"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0 and result.stdout.strip():
            print("System printers (via WMIC):")
            lines = result.stdout.strip().split('\n')
            for line in lines:
                line = line.strip()
                if line and not line.startswith('Name'):
                    print(f"  {line}")
            return True
            
    except Exception as e:
        print(f"WMIC method failed: {e}")
    
    print("Could not retrieve printer list")
    return False

def test_scribus_printing():
    """Test Scribus printing capability with a sample file."""
    print("\n=== Testing Scribus Printing ===")
    
    # Look for an existing SLA file to test with
    test_files = [
        "scribus_template_proxytest1.sla",
        "test_print.sla"
    ]
    
    test_file = None
    for filename in test_files:
        if Path(filename).exists():
            test_file = Path(filename)
            break
    
    if not test_file:
        # Look in ready2Print directories
        ready_dir = Path("ready2Print")
        if ready_dir.exists():
            for sla_file in ready_dir.rglob("*.sla"):
                test_file = sla_file
                break
    
    if not test_file:
        print("✗ No SLA test files found")
        print("  Create some SLA files first using create_scribus_files.py")
        return False
    
    print(f"Testing with file: {test_file}")
    
    # Test with PDF printer (should be available on all systems)
    printer = "Microsoft Print to PDF"
    
    try:
        result = subprocess.run([
            sys.executable, "test_scribus_printer_config.py", 
            "--print-file", str(test_file), 
            "--printer", printer
        ], capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print(f"✓ Test print successful to {printer}")
            print("  Scribus native printing is working!")
            return True
        else:
            print(f"✗ Test print failed (return code {result.returncode})")
            if result.stderr:
                print(f"  Error: {result.stderr.strip()}")
            return False
            
    except Exception as e:
        print(f"✗ Test print error: {e}")
        return False

def show_usage_examples():
    """Show usage examples for native Scribus printing."""
    print("\n=== Usage Examples ===")
    
    print("1. Create and print cards using native Scribus printing:")
    print("   python create_scribus_files.py your_deck.xml --print --print-method scribus --printer \"Your Printer Name\"")
    
    print("\n2. Print to PDF for testing:")
    print("   python create_scribus_files.py your_deck.xml --print --print-method scribus --printer \"Microsoft Print to PDF\"")
    
    print("\n3. Save printer preference for future use:")
    print("   python create_scribus_files.py your_deck.xml --printer \"Your Printer\" --save-printer")
    print("   python create_scribus_files.py your_deck.xml --print --print-method scribus  # Uses saved printer")
    
    print("\n4. Test specific printer with existing SLA files:")
    print("   python test_scribus_printer_config.py --print-file \"path/to/file.sla\" --printer \"Your Printer\"")
    
    print("\n5. Check printer configuration:")
    print("   python test_scribus_printer_config.py --test-config")

def show_advantages():
    """Show advantages of native Scribus printing."""
    print("\n=== Advantages of Native Scribus Printing ===")
    
    advantages = [
        "Perfect layout preservation - uses Scribus's exact rendering engine",
        "No PDF conversion artifacts or scaling issues", 
        "Direct printer communication with proper color management",
        "Preserves all template positioning and scaling exactly",
        "Handles complex layouts and embedded images properly",
        "Uses Scribus's native print dialog settings and optimizations",
        "Eliminates cropping issues from PDF export/import process"
    ]
    
    for i, advantage in enumerate(advantages, 1):
        print(f"  {i}. {advantage}")

def main():
    """Main setup and test routine."""
    print("Scribus Native Printing Setup & Test")
    print("=" * 40)
    
    # Check Scribus
    scribus_ok = check_scribus_installation()
    
    # List printers
    list_available_printers()
    
    # Test printing if Scribus is available
    if scribus_ok:
        test_ok = test_scribus_printing()
        
        if test_ok:
            print("\n✓ Setup Complete! Native Scribus printing is ready.")
        else:
            print("\n⚠ Setup issues detected. Check Scribus installation and printer availability.")
    else:
        print("\n✗ Setup failed. Scribus is not properly installed or accessible.")
    
    # Show usage info
    show_advantages()
    show_usage_examples()
    
    print("\n" + "=" * 40)
    print("For more details, see SCRIBUS_PRINTING_METHODS.md")

if __name__ == "__main__":
    main()