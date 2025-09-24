import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from find_matching_image import find_matching_image

def find_all_matching_cards(xml_file_path, images_dir_path):
    """
    Check if all cards in the XML file can be found in the images directory.
    
    Args:
        xml_file_path: Path to the XML file
        images_dir_path: Path to the images directory
    
    Returns:
        Tuple of (found_cards, missing_cards)
    """
    xml_file = Path(xml_file_path)
    images_dir = Path(images_dir_path)
    
    if not xml_file.exists():
        print(f"Error: XML file not found: {xml_file}")
        return [], []
    
    if not images_dir.exists():
        print(f"Error: Images directory not found: {images_dir}")
        return [], []
    
    try:
        # Parse XML
        tree = ET.parse(str(xml_file))
        root = tree.getroot()
        
        found_cards = []
        missing_cards = []
        
        # Check fronts section
        fronts_section = root.find("fronts")
        if fronts_section:
            for card in fronts_section.findall("card"):
                card_name_elem = card.find("name")
                if card_name_elem is None:
                    card_name_elem = card.find("n")  # Try legacy format
                
                if card_name_elem is None:
                    print(f"Warning: Card without name tag found, skipping")
                    continue
                    
                card_name = card_name_elem.text
                
                # Try to find a matching image
                found_image = find_matching_image(images_dir, card_name)
                
                if found_image:
                    found_cards.append((card_name, found_image))
                else:
                    missing_cards.append(card_name)
        
        # Check backs section if it exists
        backs_section = root.find("backs")
        if backs_section:
            for card in backs_section.findall("card"):
                card_name_elem = card.find("name")
                if card_name_elem is None:
                    card_name_elem = card.find("n")  # Try legacy format
                
                if card_name_elem is None:
                    print(f"Warning: Card without name tag found, skipping")
                    continue
                    
                card_name = card_name_elem.text
                
                # Try to find a matching image
                found_image = find_matching_image(images_dir, card_name)
                
                if found_image:
                    found_cards.append((card_name, found_image))
                else:
                    missing_cards.append(card_name)
        
        return found_cards, missing_cards
    
    except Exception as e:
        print(f"Error processing XML file: {e}")
        import traceback
        traceback.print_exc()
        return [], []

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="Check if all cards in the XML file can be found in the images directory.")
    parser.add_argument("xml_file", help="Path to the XML file")
    parser.add_argument("images_dir", help="Path to the images directory")
    
    args = parser.parse_args()
    
    found_cards, missing_cards = find_all_matching_cards(args.xml_file, args.images_dir)
    
    print("\n=== Found Cards ===")
    for card_name, image_path in found_cards:
        print(f"{card_name} -> {image_path}")
    
    print(f"\nTotal found: {len(found_cards)} cards")
    
    print("\n=== Missing Cards ===")
    for card_name in missing_cards:
        print(card_name)
    
    print(f"\nTotal missing: {len(missing_cards)} cards")

if __name__ == "__main__":
    main()