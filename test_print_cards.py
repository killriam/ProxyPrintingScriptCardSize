import os
import sys
import argparse
from pathlib import Path
from Print_cards_sm import main as print_cards_main

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Test the card printing script without actually printing')
parser.add_argument('--no-download', action='store_true', help='Skip downloading missing images')
args = parser.parse_args()

# Get the script directory
script_dir = Path(__file__).resolve().parent

# Look for XML files in the 'cards xml' directory
xml_dir = script_dir / "cards xml"

if not xml_dir.exists():
    print(f"Error: 'cards xml' directory not found at {xml_dir}")
    sys.exit(1)

# Get all XML files in the directory
xml_files = list(xml_dir.glob("*.xml"))

if not xml_files:
    print(f"No XML files found in {xml_dir}")
    sys.exit(1)

print(f"Found {len(xml_files)} XML files:")
for i, xml_file in enumerate(xml_files):
    print(f"{i+1}. {xml_file.name}")

# Prompt user to select an XML file
try:
    selection = int(input("\nEnter the number of the XML file to use (or 0 to exit): "))
    if selection == 0:
        sys.exit(0)
    selected_xml = xml_files[selection - 1]
except (ValueError, IndexError):
    print("Invalid selection")
    sys.exit(1)

print(f"\nSelected: {selected_xml}")

# Prompt for images directory
images_dir = input("\nEnter the path to the images directory (leave empty for default): ")
if not images_dir:
    images_dir = None  # Use default

print("\nRunning in test mode (no printing)...")
sys.argv.extend(['--no-print'])  # Add the --no-print flag to sys.argv

# Add --no-download flag if specified
if args.no_download:
    sys.argv.extend(['--no-download'])
    print("Download of missing images disabled.")

# Call the main function from Print_cards_sm.py
print_cards_main(xml_file_path=str(selected_xml), images_dir_path=images_dir)

print("\nTest completed. Check the output above for any errors.")