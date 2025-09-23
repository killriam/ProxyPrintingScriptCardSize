import os
import sys
from pathlib import Path
import traceback
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test the Print_cards_sm.py script.')
group = parser.add_mutually_exclusive_group()
group.add_argument('-d', '--deck', dest='deck_list_path', 
                  help='Path to a deck list file to test')
group.add_argument('-x', '--xml', dest='xml_file_path',
                  help='Path to an XML file to test')
parser.add_argument('--clean', action='store_true', 
                  help='Clean the test directory before running')

args = parser.parse_args()

# If no args provided but command line arguments exist, use first positional as deck list (for backwards compatibility)
if not (args.deck_list_path or args.xml_file_path) and len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
    args.deck_list_path = sys.argv[1]

# Default to doctor_who_deck.txt if no arguments provided
if not (args.deck_list_path or args.xml_file_path):
    args.deck_list_path = "doctor_who_deck.txt"

# Make sure the mtg_test directory is available
script_dir = Path(__file__).resolve().parent
mtg_test_dir = script_dir / "mtg_test"

# Clean up previous test folders if requested
if args.clean and mtg_test_dir.exists():
    import shutil
    print(f"Cleaning up test directory: {mtg_test_dir}")
    shutil.rmtree(mtg_test_dir)
    mtg_test_dir.mkdir(exist_ok=True)
else:
    mtg_test_dir.mkdir(exist_ok=True)

# Create base directories
(mtg_test_dir / "images").mkdir(exist_ok=True)
(mtg_test_dir / "prints").mkdir(exist_ok=True)

# Set environment variables to use the test directory
os.environ["MTG_DIR"] = str(mtg_test_dir)
os.environ["PRINTER_NAME"] = "MOCK_PRINTER"  # This won't be found and will fail gracefully

print(f"Using test directory: {mtg_test_dir}")

# Mock the printer function to avoid actual printing
import importlib.util
spec = importlib.util.spec_from_file_location("print_cards", script_dir / "Print_cards_sm.py")
print_cards = importlib.util.module_from_spec(spec)

# Before executing, replace the printer function with our mock
def mock_send_image_to_printer(image_path, printer_name, *args, **kwargs):
    print(f"MOCK PRINTER: Would print {image_path} to {printer_name}")
    return True

# Execute the module
try:
    spec.loader.exec_module(print_cards)
    
    # Replace the printer function
    original_printer_func = print_cards.send_image_to_printer
    print_cards.send_image_to_printer = mock_send_image_to_printer
    
    # Run the main function with the appropriate arguments
    if args.deck_list_path:
        deck_name = Path(args.deck_list_path).stem
        print(f"\nTesting Print_cards_sm.py with deck list: {args.deck_list_path}")
        print(f"Deck name for subfolder: {deck_name}")
        print("="*60)
        print_cards.main(deck_list_path=args.deck_list_path)
        
        # Print out what files were downloaded
        deck_images_dir = mtg_test_dir / "images" / deck_name
        if deck_images_dir.exists():
            print("\nDownloaded images in subfolder:")
            image_count = 0
            for image_file in deck_images_dir.glob("*.jpg"):
                print(f"  - {image_file.name}")
                image_count += 1
            print(f"Total images downloaded: {image_count}")
        
        # Print XML file location
        xml_file = mtg_test_dir / f"cards_{deck_name}.xml"
        if xml_file.exists():
            print(f"\nXML file created: {xml_file}")
    
    elif args.xml_file_path:
        xml_name = Path(args.xml_file_path).stem
        print(f"\nTesting Print_cards_sm.py with XML file: {args.xml_file_path}")
        print("="*60)
        print_cards.main(xml_file_path=args.xml_file_path)
        
        # Print out the subfolder name derived from XML
        if xml_name.startswith("cards_"):
            xml_name = xml_name[6:]  # Remove "cards_" prefix if present
        
        # Set deck_name for later use with the XML file's stem name
        deck_name = xml_name
        
        print(f"\nXML file used: {args.xml_file_path}")
        print(f"Subfolder derived from XML: {xml_name}")
        
    # Restore original function
    print_cards.send_image_to_printer = original_printer_func
    
    # Print out what files were downloaded
    deck_images_dir = mtg_test_dir / "images" / deck_name
    if deck_images_dir.exists():
        print("\nDownloaded images in subfolder:")
        image_count = 0
        for image_file in deck_images_dir.glob("*.jpg"):
            print(f"  - {image_file.name}")
            image_count += 1
        print(f"Total images downloaded: {image_count}")
    
    # Print XML file location
    xml_file = mtg_test_dir / f"cards_{deck_name}.xml"
    if xml_file.exists():
        print(f"\nXML file created: {xml_file}")
        
    print("\nTest complete!")

except Exception as e:
    print(f"Error during test: {e}")
    traceback.print_exc()