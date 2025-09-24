#!/usr/bin/env python3

import os
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import json
import shlex
import time

# Import library-based processor if available
try:
    from scribus_library_advanced import ScribusLibraryProcessor
    LIBRARY_PROCESSOR_AVAILABLE = True
except ImportError:
    LIBRARY_PROCESSOR_AVAILABLE = False

SETTINGS_FILE = Path(__file__).with_suffix('.settings.json')

def load_settings():
    try:
        if SETTINGS_FILE.exists():
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_settings(data: dict):
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False

def list_windows_printers():
    """Return a list of installed Windows printer names using PowerShell."""
    try:
        # Use PowerShell Get-Printer and return names
        cmd = ['powershell', '-NoProfile', '-Command', 'Get-Printer | Select-Object -ExpandProperty Name']
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = proc.stdout or ''
        printers = [line.strip() for line in out.splitlines() if line.strip()]
        return printers
    except Exception:
        return []

def choose_printer_interactive():
    printers = list_windows_printers()
    if not printers:
        print('No Windows printers detected.')
        return None
    print('Select a printer:')
    for i, p in enumerate(printers, 1):
        print(f'  {i}) {p}')
    try:
        choice = input('Printer number (or Enter to cancel): ').strip()
        if not choice:
            return None
        idx = int(choice) - 1
        if 0 <= idx < len(printers):
            return printers[idx]
    except Exception:
        pass
    return None

def create_scribus_files_from_xml(
    xml_file_path,
    template_sla_path,
    output_dir=None,
    base_dir=None,
    print_files=False,
    printer_name=None,
    copies=1,
    headless=True,
    print_method='pdf',
):
    """
    Create a Scribus file for each card in an XML file.
    
    Args:
        xml_file_path: Path to the XML file containing card information.
        template_sla_path: Path to the Scribus template file.
        output_dir: Subfolder name under ready2Print/ for Scribus files. If None, uses deck name.
        base_dir: Base directory for the project. If None, uses script directory.
        print_files: Whether to print the generated Scribus files.
    """
    # Set up base directories
    script_dir = Path(__file__).resolve().parent
    base_dir = Path(base_dir) if base_dir else script_dir
    mtg_dir = Path(os.environ.get("MTG_DIR", base_dir / "mtg"))
    
    # Load XML file
    try:
        xml_path = Path(xml_file_path)
        if not xml_path.is_absolute():
            xml_path = base_dir / xml_path
            
        if not xml_path.exists():
            raise FileNotFoundError(f"XML file not found: {xml_path}")
        
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        # Determine deck name from XML filename
        deck_name = xml_path.stem
        if deck_name.startswith("cards_"):
            deck_name = deck_name[6:]  # Remove "cards_" prefix if present
            
        # Determine output directory - always under ready2Print/
        ready2print_dir = base_dir / "ready2Print"
        if output_dir:
            output_path = ready2print_dir / output_dir
        else:
            output_path = ready2print_dir / deck_name
            
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Load template file
        template_path = Path(template_sla_path)
        if not template_path.is_absolute():
            template_path = base_dir / template_path
            
        if not template_path.exists():
            raise FileNotFoundError(f"Template file not found: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as file:
            template_content = file.read()
        
        # Find image file pattern in template
        image_pattern = r'PFILE="([^"]*)"'
        template_image = re.search(image_pattern, template_content)
        
        if not template_image:
            raise ValueError(f"Could not find PFILE attribute in template file")
            
        template_image_path = template_image.group(1)
        print(f"Found template image path: {template_image_path}")
        
        # Check for the fronts section
        fronts = root.find("fronts")
        if fronts is None:
            raise ValueError("No 'fronts' section found in XML file")
        
        # Process cards in the fronts section
        cards_processed = 0
        created_files = []
        for card in fronts.findall("card"):
            # Get card name (full filename) and ID
            card_name_elem = card.find("name")
            if card_name_elem is None:
                card_name_elem = card.find("n")  # Try legacy format
                
            if card_name_elem is None:
                print(f"Warning: Card without name tag found, skipping")
                continue
                
            card_filename = card_name_elem.text
            
            # Extract slots information (for multiple copies)
            slots_elem = card.find("slots")
            if slots_elem is None or not slots_elem.text:
                slots = [1]  # Default to one copy if no slots defined
            else:
                try:
                    slots_text = slots_elem.text.strip()
                    slots = [int(s.strip()) for s in slots_text.split(',') if s.strip()]
                except ValueError:
                    print(f"Warning: Invalid slots format for card {card_filename}, defaulting to one copy")
                    slots = [1]
            
            # Check if this is a mtg_test xml file
            is_test_xml = "mtg_test" in str(xml_path)
            
            # Create image path based on whether it's in mtg_test or mtg
            if is_test_xml:
                image_path = f"mtg_test/images/{deck_name}/{card_filename}"
                # Check if the image file exists (as a verification step)
                full_image_path = base_dir / "mtg_test" / "images" / deck_name / card_filename
            else:
                image_path = f"mtg/images/{deck_name}/{card_filename}"
                # Check if the image file exists (as a verification step)
                full_image_path = mtg_dir / "images" / deck_name / card_filename
                
            if not full_image_path.exists():
                print(f"Warning: Image file not found: {full_image_path}")
                # Still proceed, as image might be added later
            
            # Compute path to use inside SLA (relative to output directory so Scribus resolves correctly)
            try:
                pfile_rel = os.path.relpath(full_image_path, start=output_path)
            except Exception:
                # Fallback: use original image_path string
                pfile_rel = image_path
            # Normalize to forward slashes for SLA XML
            pfile_rel = pfile_rel.replace('\\', '/')

            # Create a Scribus file for each slot/copy
            for slot in slots:
                # Replace only the first PFILE occurrence with the relative image path
                # (some templates contain multiple image pageobjects; updating only the
                # first keeps any intentional additional placeholders untouched)
                new_content = re.sub(image_pattern, f'PFILE="{pfile_rel}"', template_content, count=1)

                # Create output filename
                output_file = output_path / f"{os.path.splitext(card_filename)[0]}_{slot}.sla"

                # Write the new Scribus file
                with open(output_file, 'w', encoding='utf-8') as file:
                    file.write(new_content)

                print(f"Created Scribus file: {output_file} (image -> {pfile_rel})")
                created_files.append(output_file)
                cards_processed += 1
                
        print(f"\nProcessing complete. Created {cards_processed} Scribus files in {output_path}")
        
        # If print_files flag is set or ask the user interactively
        if print_files or (input("\nPrint all Scribus files now? (y/N): ").lower().strip() == 'y'):
            if print_method == 'manual':
                open_scribus_files_manually(
                    created_files,
                    printer_name=printer_name,
                )
            elif print_method == 'library':
                success = print_scribus_files_via_library(
                    created_files,
                    printer_name=printer_name,
                    copies=copies,
                )
                # If library method fails, fall back to PDF method
                if not success:
                    print("\nLibrary method failed. Falling back to PDF export method...")
                    success = print_scribus_files_via_pdf(
                        created_files,
                        printer_name=printer_name,
                        copies=copies,
                        headless=headless,
                    )
            elif print_method == 'pdf':
                success = print_scribus_files_via_pdf(
                    created_files,
                    printer_name=printer_name,
                    copies=copies,
                    headless=headless,
                )
                # If PDF method fails, fall back to direct Scribus printing
                if not success:
                    print("\nPDF export failed. Falling back to direct Scribus printing...")
                    print_scribus_files(
                        created_files,
                        printer_name=printer_name,
                        copies=copies,
                        headless=headless,
                    )
            else:
                print_scribus_files(
                    created_files,
                    printer_name=printer_name,
                    copies=copies,
                    headless=headless,
                )
        
    except Exception as e:
        import traceback
        print(f"Error creating Scribus files: {e}")
        traceback.print_exc()
        return False
        
    return True

def print_scribus_files_via_library(sla_files, printer_name=None, copies=1):
    """Print Scribus .sla files using pure Python libraries (no Scribus command line).
    
    This method uses ReportLab and other Python libraries to parse SLA files
    and convert them to PDF for printing, avoiding the need for Scribus command line.
    
    Args:
        sla_files (list[Path]): Files to process and print.
        printer_name (str|None): Explicit printer name. If None, use default.
        copies (int): Number of copies per file.
    """
    if not LIBRARY_PROCESSOR_AVAILABLE:
        print("Library processor not available. Install required libraries:")
        print("pip install reportlab pillow pywin32")
        return False
    
    try:
        print(f"Using library-based printing for {len(sla_files)} file(s)...")
        
        # Resolve printer name
        target_printer = None
        if printer_name:
            target_printer = printer_name
        elif os.environ.get("PRINTER_NAME"):
            target_printer = os.environ["PRINTER_NAME"]
        else:
            # Try to load saved printer from settings
            saved = load_settings().get('printer_name')
            if saved:
                target_printer = saved
            else:
                # No saved printer, prompt user to select from Windows printers
                chosen = choose_printer_interactive()
                if chosen:
                    target_printer = chosen
                    # merge with existing settings
                    s = load_settings()
                    s['printer_name'] = chosen
                    save_settings(s)
        
        print(f"Target printer: {target_printer}")
        
        # Create library processor
        processor = ScribusLibraryProcessor()
        
        # Process all files
        sla_file_paths = [str(f) for f in sla_files]
        success = processor.print_sla_files_batch(sla_file_paths, target_printer, copies)
        
        if success:
            print("✓ Library-based printing completed successfully!")
        else:
            print("✗ Some files failed during library-based printing")
        
        return success
        
    except Exception as e:
        import traceback
        print(f"Error during library-based printing: {e}")
        traceback.print_exc()
        return False

def print_scribus_files(sla_files, printer_name=None, copies=1, headless=True):
    """Batch print Scribus .sla files using a simplified approach.
    
    We'll try multiple methods in order of reliability:
    1. Scribus with Python helper (current method)
    2. Scribus GUI mode with print dialog
    3. Set Windows default printer and use Scribus print verb
    """
    try:
        if not sla_files:
            print("No Scribus files to print.")
            return False

        total = len(sla_files)
        print(f"Preparing to print {total} Scribus file(s)...")

        scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
        try:
            result = subprocess.run([scribus_cmd, "--version"], capture_output=True, text=True, check=False)
            ver = result.stdout.strip() if result.stdout else "(version unknown)"
            print(f"Using Scribus command: {scribus_cmd} {ver}")
        except FileNotFoundError:
            print("ERROR: Scribus executable not found. Set SCRIBUS_CMD env var or add to PATH.")
            return False

        # Resolve printer name using same logic as before
        target_printer = None
        if printer_name:
            target_printer = printer_name
        elif os.environ.get("PRINTER_NAME"):
            target_printer = os.environ["PRINTER_NAME"]
        else:
            # Try to load saved printer from settings
            saved = load_settings().get('printer_name')
            if saved:
                target_printer = saved
            else:
                # No saved printer, prompt user to select from Windows printers
                chosen = choose_printer_interactive()
                if chosen:
                    target_printer = chosen
                    # merge with existing settings
                    s = load_settings()
                    s['printer_name'] = chosen
                    save_settings(s)

        print(f"Target printer: {target_printer}")

        # Method 1: Try Windows print command (simplest)
        failures = 0
        for idx, sla_file in enumerate(sla_files, 1):
            print(f"[{idx}/{total}] Printing: {sla_file.name}")
            
            for attempt, method in enumerate([
                # Method 1: Direct print command
                lambda f: subprocess.run(['print', f'/D:{target_printer}', str(f)], capture_output=True, text=True, timeout=30),
                # Method 2: PowerShell Out-Printer on the file content
                lambda f: subprocess.run(['powershell', '-Command', f'Get-Content "{f}" -Raw | Out-Printer -Name "{target_printer}"'], capture_output=True, text=True, timeout=30),
                # Method 3: Open with default application
                lambda f: subprocess.run(['cmd', '/c', 'start', '/min', str(f)], capture_output=True, text=True, timeout=15),
            ], 1):
                try:
                    result = method(sla_file)
                    if result.returncode == 0:
                        print(f"  Success via method {attempt}")
                        break
                    elif attempt == 3:
                        print(f"  All methods failed for {sla_file.name}")
                        failures += 1
                except Exception as e:
                    if attempt == 3:
                        print(f"  Error printing {sla_file.name}: {e}")
                        failures += 1

        if failures > 0:
            print(f"Some files failed to print: {failures}/{total}")
            print("Alternative: Open the SLA files manually in Scribus and print them.")
            return False
        else:
            print("All files sent for printing.")
            return True

    except Exception as print_error:
        import traceback
        print(f"Error during printing: {print_error}")
        traceback.print_exc()
        return False

def print_scribus_files_via_pdf(sla_files, printer_name=None, copies=1, headless=True):
    """Export Scribus .sla files to PDF, then print the PDFs using Windows system calls.
    
    This is more reliable than direct Scribus printing on Windows as it avoids
    driver dialog issues and uses standard PDF printing.
    
    Args:
        sla_files (list[Path]): Files to export and print.
        printer_name (str|None): Explicit printer name. If None, use saved setting or prompt.
        copies (int): Number of copies per file.
        headless (bool): Run Scribus with -g -ns (no GUI, no splash).
    """
    try:
        if not sla_files:
            print("No Scribus files to print.")
            return False

        total = len(sla_files)
        print(f"Preparing to export and print {total} Scribus file(s) via PDF...")

        scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
        try:
            result = subprocess.run([scribus_cmd, "--version"], capture_output=True, text=True, check=False)
            ver = result.stdout.strip() if result.stdout else "(version unknown)"
            print(f"Using Scribus command: {scribus_cmd} {ver}")
        except FileNotFoundError:
            print("ERROR: Scribus executable not found. Set SCRIBUS_CMD env var or add to PATH.")
            return False

        # Resolve printer name using same logic as direct printing
        target_printer = None
        if printer_name:
            target_printer = printer_name
        elif os.environ.get("PRINTER_NAME"):
            target_printer = os.environ["PRINTER_NAME"]
        else:
            # Try to load saved printer from settings
            saved = load_settings().get('printer_name')
            if saved:
                target_printer = saved
            else:
                # No saved printer, prompt user to select from Windows printers
                chosen = choose_printer_interactive()
                if chosen:
                    target_printer = chosen
                    # merge with existing settings
                    s = load_settings()
                    s['printer_name'] = chosen
                    save_settings(s)

        if not target_printer:
            print("ERROR: No printer specified or available.")
            return False

        print(f"Target printer: {target_printer}")

        # Create PDF export helper script
        pdf_export_script = r"""#!/usr/bin/env python3
import os, sys

def main():
    try:
        import scribus
    except ImportError:
        print('Scribus module not available', file=sys.stderr)
        return 1
        
    if not scribus.haveDoc():
        print('No document open', file=sys.stderr)
        return 1
    
    try:
        # Get output path from environment
        pdf_path = os.environ.get('SCRIBUS_PDF_OUTPUT')
        if not pdf_path:
            print('No PDF output path specified', file=sys.stderr)
            return 1
        
        print(f'Exporting to: {pdf_path}', file=sys.stderr)
        
        # Use the simple saveAsPDF function with just the filename
        result = scribus.saveAsPDF(pdf_path)
        
        # Check if file was actually created
        if os.path.exists(pdf_path):
            size = os.path.getsize(pdf_path)
            print(f'PDF created successfully: {pdf_path} ({size} bytes)', file=sys.stderr)
            return 0
        else:
            print('PDF file was not created', file=sys.stderr)
            return 2
            
    except Exception as e:
        print(f'Error during PDF export: {e}', file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
"""

        # Determine output directory for PDFs
        if sla_files:
            pdf_dir = sla_files[0].parent / 'pdfs'
            pdf_dir.mkdir(exist_ok=True)
        else:
            pdf_dir = Path.cwd() / 'pdfs'
            pdf_dir.mkdir(exist_ok=True)

        with tempfile.NamedTemporaryFile(suffix="_scribus_pdf_export.py", delete=False, mode="w", encoding="utf-8") as helper_fp:
            helper_fp.write(pdf_export_script)
            script_path = helper_fp.name

        try:
            failures = 0
            exported_pdfs = []

            # Step 1: Export all SLA files to PDF
            print("Step 1: Exporting SLA files to PDF...")
            for idx, sla_file in enumerate(sla_files, 1):
                print(f"[{idx}/{total}] Exporting: {sla_file.name}")
                
                # Generate PDF filename
                pdf_name = sla_file.stem + '.pdf'
                pdf_path = pdf_dir / pdf_name
                
                cmd = [scribus_cmd]
                if headless:
                    cmd += ["-g", "-ns"]
                cmd += [str(sla_file), "-py", script_path]

                env = os.environ.copy()
                env["SCRIBUS_PDF_OUTPUT"] = str(pdf_path)

                proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
                
                if proc.returncode != 0 or not pdf_path.exists():
                    failures += 1
                    print(f"  FAILED to export {sla_file.name}")
                    if proc.stderr:
                        print(f"    stderr: {proc.stderr.strip()}")
                    if proc.stdout:
                        print(f"    stdout: {proc.stdout.strip()}")
                else:
                    print(f"  Exported: {pdf_name}")
                    exported_pdfs.append(pdf_path)

            if failures > 0:
                print(f"Export failures: {failures}/{total}. Continuing with {len(exported_pdfs)} successful exports.")
            
            if not exported_pdfs:
                print("No PDFs were successfully exported. Cannot proceed with printing.")
                return False

            # Step 2: Print the exported PDFs
            print(f"\nStep 2: Printing {len(exported_pdfs)} PDF file(s)...")
            print_failures = 0
            
            for idx, pdf_path in enumerate(exported_pdfs, 1):
                print(f"[{idx}/{len(exported_pdfs)}] Printing: {pdf_path.name}")
                
                # Try multiple copies if requested
                for copy_num in range(copies):
                    copy_suffix = f" (copy {copy_num + 1})" if copies > 1 else ""
                    
                    # Try SumatraPDF first (silent printing), then fallback to shell print
                    success = False
                    
                    # Method 1: Windows lpr command (most reliable)
                    try:
                        lpr_cmd = ['lpr', '-S', 'localhost', '-P', target_printer, str(pdf_path)]
                        lpr_result = subprocess.run(lpr_cmd, capture_output=True, text=True, timeout=30)
                        if lpr_result.returncode == 0:
                            print(f"  Printed via lpr{copy_suffix}")
                            success = True
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        pass  # Try next method
                    
                    # Method 2: SumatraPDF (if available)
                    if not success:
                        try:
                            sumatrapdf_result = subprocess.run([
                                'SumatraPDF.exe', '-print-to', target_printer, str(pdf_path)
                            ], capture_output=True, text=True, timeout=30)
                            if sumatrapdf_result.returncode == 0:
                                print(f"  Printed via SumatraPDF{copy_suffix}")
                                success = True
                        except (subprocess.TimeoutExpired, FileNotFoundError):
                            pass  # Try next method
                    
                    # Method 3: PowerShell with direct printer targeting
                    if not success:
                        try:
                            ps_cmd = [
                                'powershell', '-NoProfile', '-Command',
                                f'Get-Content "{pdf_path}" -Raw | Out-Printer -Name "{target_printer}"'
                            ]
                            ps_result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=15)
                            if ps_result.returncode == 0:
                                print(f"  Printed via PowerShell Out-Printer{copy_suffix}")
                                success = True
                        except subprocess.TimeoutExpired:
                            pass
                    
                    if not success:
                        print(f"  FAILED to print{copy_suffix}")
                        print_failures += 1

            if print_failures > 0:
                print(f"Print failures: {print_failures}. Check printer status and PDFs in: {pdf_dir}")
            else:
                print("All files printed successfully.")
            
            return print_failures == 0

        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    except Exception as print_error:
        import traceback
        print(f"Error during PDF export/print: {print_error}")
        traceback.print_exc()
        return False

def open_scribus_files_manually(sla_files, printer_name=None):
    """Open Scribus files one by one for manual printing.
    
    Args:
        sla_files (list[Path]): Files to open.
        printer_name (str|None): Suggested printer name to use.
    """
    if not sla_files:
        print("No Scribus files to open.")
        return False
        
    total = len(sla_files)
    print(f"Opening {total} Scribus file(s) for manual printing...")
    if printer_name:
        print(f"Suggested printer: {printer_name}")
    print("For each file that opens:")
    print("1. Press Ctrl+P or go to File → Print")
    print("2. Select your printer and adjust settings")
    print("3. Click Print")
    print("4. Close the file (Ctrl+W)")
    print()
    
    for idx, sla_file in enumerate(sla_files, 1):
        print(f"[{idx}/{total}] Opening: {sla_file.name}")
        try:
            # Open with the default application (should be Scribus)
            os.startfile(str(sla_file))
            if idx < total:
                input("Press Enter when ready for the next file...")
        except Exception as e:
            print(f"  Failed to open {sla_file.name}: {e}")
    
    print("All files have been opened. Manual printing complete.")
    return True

def main():
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Create Scribus files for each card in an XML file.')
    parser.add_argument('xml_file', help='Path to the XML file with card information')
    parser.add_argument('--template', '-t', dest='template_file', default='scribus_template_proxytest1.sla',
                       help='Path to the Scribus template file (default: scribus_template_proxytest1.sla)')
    parser.add_argument('--output', '-o', dest='output_dir',
                       help='Subfolder name under ready2Print/ for Scribus files (default: deck name)')
    parser.add_argument('--base-dir', '-b', dest='base_dir',
                       help='Base directory for the project')
    parser.add_argument('--print', '-p', dest='print_files', action='store_true',
                       help='Automatically print all generated Scribus files')
    parser.add_argument('--printer', dest='printer_name', help='Explicit printer name (overrides PRINTER_NAME env)')
    parser.add_argument('--save-printer', dest='save_printer', action='store_true', help='Save the provided or interactively chosen printer into settings')
    parser.add_argument('--show-printer', dest='show_printer', action='store_true', help='Show the currently saved printer in settings')
    parser.add_argument('--reset-printer', dest='reset_printer', action='store_true', help='Clear the saved printer setting')
    parser.add_argument('--copies', dest='copies', type=int, default=1, help='Number of copies per file (default 1)')
    parser.add_argument('--no-headless', dest='no_headless', action='store_true', help='Show Scribus GUI while printing')
    parser.add_argument('--print-method', dest='print_method', choices=['scribus', 'pdf', 'library', 'manual'], default='library', help='Print method: scribus (direct), pdf (export then print), library (pure Python), or manual (open files for manual printing)')
    
    args = parser.parse_args()
    
    # Handle settings flags
    if args.show_printer:
        s = load_settings()
        p = s.get('printer_name')
        if p:
            print('Saved printer:', p)
        else:
            print('No printer saved in settings.')
        return

    if args.reset_printer:
        s = load_settings()
        if 'printer_name' in s:
            del s['printer_name']
            save_settings(s)
            print('Saved printer cleared.')
        else:
            print('No saved printer to clear.')
        return

    # If save-printer is requested without an explicit printer, prompt for one
    if args.save_printer and not args.printer_name:
        chosen = choose_printer_interactive()
        if chosen:
            s = load_settings()
            s['printer_name'] = chosen
            save_settings(s)
            print('Saved printer:', chosen)
        else:
            print('No printer chosen; not saved.')
        return

    # If an explicit printer is provided and --save-printer is set, persist it
    if args.printer_name and args.save_printer:
        s = load_settings()
        s['printer_name'] = args.printer_name
        save_settings(s)
        print('Saved printer:', args.printer_name)

    # Call the main function
    create_scribus_files_from_xml(
        xml_file_path=args.xml_file,
        template_sla_path=args.template_file,
        output_dir=args.output_dir,
        base_dir=args.base_dir,
        print_files=args.print_files,
        printer_name=args.printer_name,
        copies=args.copies,
        headless=not args.no_headless,
        print_method=args.print_method,
    )

if __name__ == "__main__":
    main()