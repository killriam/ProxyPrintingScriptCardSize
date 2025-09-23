import os
import win32print
import win32ui
import win32gui
import win32con
from PIL import Image
import xml.etree.ElementTree as ET
from pathlib import Path
import requests
import time
import re
import sys
import urllib.parse

def crop_and_center_image(image_path, output_path, crop_percentage_top=0.07, crop_percentage_bottom=0.07, crop_percentage_left_right=0.07, canvas_size=(2.5 * 300, 3.5 * 300), dpi=300):
    """
    Crop the image, scale it, and center it on a rectangular canvas.
    """
    # Reduce canvas size by 8% for scaling
    canvas_width, canvas_height = canvas_size
    canvas_width = int(canvas_width * 0.92)
    canvas_height = int(canvas_height * 0.92)

    # Open the image
    img = Image.open(image_path)
    img_width, img_height = img.size

    # Crop the image by the specified percentages
    crop_left_right = int(img_width * crop_percentage_left_right)
    crop_top = int(img_height * crop_percentage_top)
    crop_bottom = int(img_height * crop_percentage_bottom)
    img = img.crop((crop_left_right, crop_top, img_width - crop_left_right, img_height - crop_bottom))

    # Calculate the scaling factor to fit the image within the canvas
    scale_x = canvas_width / img.width
    scale_y = canvas_height / img.height
    scale = min(scale_x, scale_y)

    # Scale the image
    new_width = int(img.width * scale)
    new_height = int(img.height * scale)
    img = img.resize((new_width, new_height), Image.LANCZOS)

    # Create a blank white canvas
    canvas = Image.new("RGB", (int(canvas_width), int(canvas_height)), (255, 255, 255))

    # Center the scaled image on the canvas
    x_offset = (canvas_width - new_width) // 2
    y_offset = (canvas_height - new_height) // 2
    canvas.paste(img, (int(x_offset), int(y_offset)))

    # Save the final image
    canvas.save(output_path, "BMP")
    print(f"Saved cropped and centered image to {output_path}")

def send_image_to_printer(image_path, printer_name, target_size=(2.5 * 300, 3.5 * 300), dpi=300):
    """
    Send image to printer with adjusted size and position compensation.
    """
    printer_dc = None
    mem_dc = None
    hbitmap = None
    old_bitmap = None

    try:
        # Open the printer device context
        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(printer_name)

        # Get printer DPI and physical characteristics
        printer_dpi_x = printer_dc.GetDeviceCaps(win32con.LOGPIXELSX)
        printer_dpi_y = printer_dc.GetDeviceCaps(win32con.LOGPIXELSY)
        
        # Physical offsets from edge of paper to printable area
        physical_offset_x = printer_dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        physical_offset_y = printer_dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
        
        # Calculate target size in printer units with 6% reduction (adjusted from 16%)
        # Less aggressive reduction since original was too small
        card_width_inches = 2.5 * 0.94  # Reduce width by 6%
        card_height_inches = 3.5 * 0.94  # Reduce height by 6%
        
        card_width_du = int(card_width_inches * printer_dpi_x)
        card_height_du = int(card_height_inches * printer_dpi_y)

        # Get physical page dimensions
        page_width_du = printer_dc.GetDeviceCaps(win32con.PHYSICALWIDTH)
        page_height_du = printer_dc.GetDeviceCaps(win32con.PHYSICALHEIGHT)

        # Calculate centering offsets, compensating for physical offsets
        x_offset = ((page_width_du - card_width_du) // 2) - physical_offset_x
        y_offset = ((page_height_du - card_height_du) // 2) - physical_offset_y

        # Load bitmap directly using LoadImage
        hbitmap = win32gui.LoadImage(
            0,
            image_path,
            win32con.IMAGE_BITMAP,
            0,
            0,
            win32con.LR_LOADFROMFILE | win32con.LR_CREATEDIBSECTION
        )

        if not hbitmap:
            raise RuntimeError("Failed to load bitmap")

        # Create a memory DC compatible with the printer DC
        mem_dc = win32gui.CreateCompatibleDC(printer_dc.GetHandleOutput())
        
        # Select bitmap into memory DC
        old_bitmap = win32gui.SelectObject(mem_dc, hbitmap)
        
        # Get source bitmap dimensions
        bitmap_info = win32gui.GetObject(hbitmap)
        
        # Start the print job
        printer_dc.StartDoc(image_path)
        printer_dc.StartPage()

        # Draw the bitmap
        win32gui.StretchBlt(
            printer_dc.GetHandleOutput(),
            x_offset,
            y_offset,
            card_width_du,
            card_height_du,
            mem_dc,
            0,
            0,
            bitmap_info.bmWidth,
            bitmap_info.bmHeight,
            win32con.SRCCOPY
        )

        # End the print job
        printer_dc.EndPage()
        printer_dc.EndDoc()

        print(f"Sent {image_path} to printer {printer_name}")

    except Exception as e:
        print(f"Error sending {image_path} to printer: {e}")
        raise

    finally:
        # Cleanup in reverse order of creation
        try:
            if old_bitmap and mem_dc:
                win32gui.SelectObject(mem_dc, old_bitmap)
            if mem_dc:
                win32gui.DeleteDC(mem_dc)
            if hbitmap:
                win32gui.DeleteObject(hbitmap)
            if printer_dc:
                printer_dc.DeleteDC()
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")


def download_card_images(deck_list_path=None, images_dir=None, delay=0.5):
    """
    Download card images from Scryfall based on a deck list text file.
    
    Args:
        deck_list_path: Path to the deck list text file. If None, uses stdin.
        images_dir: Directory to save the images to.
        delay: Delay between requests to Scryfall in seconds.
    
    Returns:
        Dictionary mapping card names to their file paths and IDs.
    """
    if images_dir is None:
        script_dir = Path(__file__).resolve().parent
        mtg_dir = Path(os.environ.get("MTG_DIR", script_dir / "mtg"))
        images_dir = mtg_dir / "images"
    
    # Ensure the images directory exists
    images_dir.mkdir(parents=True, exist_ok=True)
    
    card_lines = []
    
    # Read the deck list from file or stdin
    if deck_list_path:
        with open(deck_list_path, 'r') as file:
            card_lines = [line.strip() for line in file if line.strip()]
    else:
        print("Enter card names (one per line, empty line to finish):")
        while True:
            line = input()
            if not line:
                break
            card_lines.append(line.strip())
    
    # Process each card line (formats like "1x Card Name" or just "Card Name")
    downloaded_cards = {}
    
    for line in card_lines:
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
        
        # Parse the line: "1x Card Name (set) number"
        # Example: "1x Rose Tyler (who) 346"
        match = re.match(r'(?:(\d+)x\s+)?(.+?)\s+\(([a-zA-Z0-9]+)\)\s+(\d+)', line)
        if match:
            quantity = int(match.group(1) or 1)
            card_name = match.group(2).strip()
            set_code = match.group(3).lower()  # Scryfall uses lowercase set codes
            collector_number = match.group(4)
            
            # Construct the Scryfall API URL for exact card by collector number
            api_url = f"https://api.scryfall.com/cards/{set_code}/{collector_number}"
            
            try:
                print(f"Looking up: {card_name} ({set_code}) {collector_number}")
                response = requests.get(api_url)
                response.raise_for_status()
                card_data = response.json()
                
                # Get the image URL (use the normal size)
                image_url = card_data.get('image_uris', {}).get('normal')
                
                # For double-faced cards
                if not image_url and 'card_faces' in card_data:
                    image_url = card_data['card_faces'][0].get('image_uris', {}).get('normal')
                
                if not image_url:
                    print(f"Could not find image URL for {card_name}")
                    continue
                
                # Get the card name from the API if it differs from our input
                api_card_name = card_data.get('name', card_name)
                
                # Generate a filename with the card ID
                card_id = card_data.get('collector_number', collector_number)
                set_name = card_data.get('set', set_code).upper()
                extension = "jpg"  # Scryfall uses jpg
                filename = f"{api_card_name} ({set_name}-{card_id}).{extension}"
                file_path = images_dir / filename
                
                # Download the image if it doesn't exist
                if not file_path.exists():
                    print(f"Downloading: {api_card_name} ({set_name}-{card_id})")
                    img_response = requests.get(image_url, stream=True)
                    img_response.raise_for_status()
                    
                    with open(file_path, 'wb') as img_file:
                        for chunk in img_response.iter_content(chunk_size=8192):
                            img_file.write(chunk)
                    
                    print(f"Saved to: {file_path}")
                else:
                    print(f"Already exists: {file_path}")
                
                # Store card info for XML generation
                downloaded_cards[api_card_name] = {
                    'path': file_path,
                    'id': f"{set_name}-{card_id}",
                    'quantity': quantity
                }
                
                # Sleep to avoid rate limiting
                time.sleep(delay)
                
            except Exception as e:
                print(f"Error downloading {card_name} ({set_code} {collector_number}): {e}")
        else:
            print(f"Could not parse line: {line}")
            print("Expected format: '1x Card Name (set) collector_number'")
            print("Example: '1x Sol Ring (c21) 263'")
    
    return downloaded_cards

def update_xml_with_downloaded_cards(xml_file, downloaded_cards):
    """Update the cards.xml file with newly downloaded cards."""
    try:
        # Create new XML or load existing
        if xml_file.exists():
            tree = ET.parse(str(xml_file))
            root = tree.getroot()
            fronts = root.find("fronts")
            if fronts is None:
                fronts = ET.SubElement(root, "fronts")
        else:
            root = ET.Element("root")
            fronts = ET.SubElement(root, "fronts")
            tree = ET.ElementTree(root)
        
        # Add new cards to XML
        for card_name, card_info in downloaded_cards.items():
            # Create a new card element
            card_elem = ET.SubElement(fronts, "card")
            
            # Add name element
            name_elem = ET.SubElement(card_elem, "name")
            name_elem.text = Path(card_info['path']).name
            
            # Add id element
            id_elem = ET.SubElement(card_elem, "id")
            id_elem.text = card_info['id']
            
            # Add slots element
            slots_elem = ET.SubElement(card_elem, "slots")
            # Create slots for the quantity (e.g., "1, 2, 3" for quantity=3)
            slots_elem.text = ", ".join(str(i) for i in range(1, card_info['quantity'] + 1))
        
        # Save updated XML
        tree.write(str(xml_file), encoding="utf-8", xml_declaration=True)
        print(f"Updated XML file: {xml_file}")
        
    except Exception as e:
        print(f"Error updating XML file: {e}")
        import traceback
        traceback.print_exc()


def download_missing_images_from_xml(xml_file, images_dir, delay=0.5):
    """
    Check an XML file for card entries and download any missing images from Scryfall.
    
    Args:
        xml_file: Path to the XML file containing card information.
        images_dir: Directory to save the images to.
        delay: Delay between requests to Scryfall in seconds.
    
    Returns:
        List of successfully downloaded card paths.
    """
    if not xml_file.exists():
        print(f"XML file not found: {xml_file}")
        return []
    
    try:
        tree = ET.parse(str(xml_file))
        root = tree.getroot()
        
        # Ensure the images directory exists
        images_dir.mkdir(parents=True, exist_ok=True)
        
        downloaded_images = []
        cards_section = root.find("fronts")
        
        if cards_section is None:
            print("No 'fronts' section found in XML")
            return []
        
        for card in cards_section.findall("card"):
            # Get card name (full filename) and ID
            card_name_elem = card.find("name")
            if card_name_elem is None:
                card_name_elem = card.find("n")  # Try legacy format
                
            card_id_elem = card.find("id")
            
            if card_name_elem is None or card_id_elem is None:
                continue
            
            card_filename = card_name_elem.text
            card_id = card_id_elem.text
            
            # Skip if it's not a proper card ID or filename
            if not card_id or not card_filename:
                continue
            
            # Parse the card name and set from the filename
            # Expecting format like "Card Name (SET-ID).jpg"
            match = re.match(r'(.+) \(([A-Za-z0-9]+)-([0-9]+)\)\.jpg', card_filename)
            if not match:
                print(f"Could not parse card filename: {card_filename}")
                continue
                
            card_name = match.group(1)
            set_code = match.group(2).lower()  # Scryfall uses lowercase set codes
            collector_number = match.group(3)
            
            # Check if image already exists
            image_path = images_dir / card_filename
            if image_path.exists():
                print(f"Image already exists: {image_path}")
                continue
                
            # Construct the Scryfall API URL
            api_url = f"https://api.scryfall.com/cards/{set_code}/{collector_number}"
            
            try:
                print(f"Looking up: {card_name} ({set_code}) {collector_number}")
                response = requests.get(api_url)
                response.raise_for_status()
                card_data = response.json()
                
                # Get the image URL (use the normal size)
                image_url = card_data.get('image_uris', {}).get('normal')
                
                # For double-faced cards
                if not image_url and 'card_faces' in card_data:
                    image_url = card_data['card_faces'][0].get('image_uris', {}).get('normal')
                
                if not image_url:
                    print(f"Could not find image URL for {card_name}")
                    continue
                
                # Download the image
                print(f"Downloading: {card_name} ({set_code}-{collector_number})")
                img_response = requests.get(image_url, stream=True)
                img_response.raise_for_status()
                
                with open(image_path, 'wb') as img_file:
                    for chunk in img_response.iter_content(chunk_size=8192):
                        img_file.write(chunk)
                
                print(f"Saved to: {image_path}")
                downloaded_images.append(image_path)
                
                # Sleep to avoid rate limiting
                time.sleep(delay)
                
            except Exception as e:
                print(f"Error downloading {card_name} ({set_code} {collector_number}): {e}")
        
        return downloaded_images
        
    except Exception as e:
        print(f"Error processing XML file: {e}")
        import traceback
        traceback.print_exc()
        return []

def main(deck_list_path=None, xml_file_path=None):
    # Base directories (use MTG_DIR env var to override)
    # By default this will look for an `mtg` folder next to this script.
    script_dir = Path(__file__).resolve().parent
    mtg_dir = Path(os.environ.get("MTG_DIR", script_dir / "mtg"))

    # File paths (relative to mtg_dir)
    images_dir = mtg_dir / "images"
    output_folder = mtg_dir / "prints"
    
    # Determine XML file and subfolders based on input parameters
    if xml_file_path:
        # Use the directly specified XML file
        xml_file = Path(xml_file_path)
        if not xml_file.is_absolute():
            # If it's a relative path, make it relative to the script directory
            xml_file = script_dir / xml_file
            
        # Use the XML filename (without extension) as the subfolder name
        xml_name = xml_file.stem
        if xml_name.startswith("cards_"):
            xml_name = xml_name[6:]  # Remove "cards_" prefix if present
            
        deck_subfolder = xml_name
        images_dir = mtg_dir / "images" / deck_subfolder
        output_folder = mtg_dir / "prints" / deck_subfolder
        
        print(f"Using XML file: {xml_file}")
        print(f"Using deck-specific folders for '{deck_subfolder}':")
        print(f"  Images: {images_dir}")
        print(f"  Output: {output_folder}")
    
    elif deck_list_path:
        # Use the deck list filename (without extension) as the subfolder name
        deck_name = Path(deck_list_path).stem
        deck_subfolder = deck_name
        
        # Create deck-specific subfolders
        images_dir = mtg_dir / "images" / deck_subfolder
        output_folder = mtg_dir / "prints" / deck_subfolder
        xml_file = mtg_dir / f"cards_{deck_subfolder}.xml"
        
        print(f"Using deck-specific folders for '{deck_subfolder}':")
        print(f"  Images: {images_dir}")
        print(f"  Output: {output_folder}")
        print(f"  XML: {xml_file}")
    
    else:
        # Default to the standard cards.xml file if no parameters are provided
        xml_file = mtg_dir / "cards.xml"
        print(f"Using default XML file: {xml_file}")
    
    printer_name = os.environ.get("PRINTER_NAME", "tanker")

    # Ensure the output and images folders exist
    images_dir.mkdir(parents=True, exist_ok=True)
    output_folder.mkdir(parents=True, exist_ok=True)
    
    try:
        # Download card images from deck list if provided
        if deck_list_path and not xml_file_path:
            # If deck_list_path is None but command line arg is provided, use that
            if deck_list_path is None and len(sys.argv) > 1:
                deck_list_path = sys.argv[1]
            
            print(f"Downloading cards from deck list: {deck_list_path}")
            downloaded_cards = download_card_images(deck_list_path, images_dir)
            
            # Update the XML file with the downloaded cards
            if downloaded_cards:
                update_xml_with_downloaded_cards(xml_file, downloaded_cards)
        
        # If direct XML file is provided, download any missing images
        elif xml_file_path:
            print(f"Checking for missing images in XML: {xml_file}")
            download_missing_images_from_xml(xml_file, images_dir)
        
        # Verify XML exists
        if not xml_file.exists():
            print(f"XML file not found: {xml_file}")
            return

        # Parse the XML file
        tree = ET.parse(str(xml_file))
        root = tree.getroot()

        # Iterate over all cards in the <fronts> section
        for card in root.find("fronts").findall("card"):
            # Get card name (support both <name> and legacy <n> tags)
            card_name_elem = card.find("name")
            if card_name_elem is None:
                card_name_elem = card.find("n")  # Try legacy format
            
            if card_name_elem is None:
                print(f"Warning: Card without name tag found, skipping")
                continue
                
            card_name = card_name_elem.text
            card_id = card.find("id").text
            slots = card.find("slots").text

            # Calculate the number of copies based on slots
            slot_list = [int(slot.strip()) for slot in slots.split(",") if slot.strip().isdigit()]
            copies = len(slot_list)

            # Construct the full image path
            # Note: card_name is the full filename including extension
            image_path = images_dir / card_name

            # Generate cropped images for each copy
            if image_path.exists():
                for copy_number in range(copies):
                    output_filename = f"{card_name.rsplit('.', 1)[0]}_copy_{copy_number + 1}.bmp"
                    output_image_path = output_folder / output_filename
                    crop_and_center_image(str(image_path), str(output_image_path))

                    # Send the cropped image to the printer
                    send_image_to_printer(str(output_image_path), printer_name)
            else:
                print(f"Image not found: {image_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    import argparse
    
    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Print Magic cards from deck list or XML file.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', '--deck', dest='deck_list_path', 
                      help='Path to a deck list file to download card images and create XML')
    group.add_argument('-x', '--xml', dest='xml_file_path',
                      help='Path to an XML file with card information')
    parser.add_argument('--no-print', action='store_true',
                      help='Download cards and create XML without printing')
    
    # Add help for environment variables
    parser.epilog = '''
Environment Variables:
  MTG_DIR         Base directory for images and output (default: ./mtg)
  PRINTER_NAME    Name of the printer to use (default: tanker)

Deck List Format:
  1x Card Name (SET) Collector#
  Example: 1x Black Lotus (LEA) 1

XML Format:
  <root>
    <fronts>
      <card>
        <name>Card Name (SET-ID).jpg</name>
        <id>SET-ID</id>
        <slots>1, 2, 3</slots>
      </card>
      <!-- more cards -->
    </fronts>
  </root>
  
  Note: Legacy format using <n> tag instead of <name> is also supported.
    '''
    
    args = parser.parse_args()
    
    # If no args provided but command line arguments exist, use first positional as deck list (for backwards compatibility)
    if not (args.deck_list_path or args.xml_file_path) and len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        args.deck_list_path = sys.argv[1]
    
    main(deck_list_path=args.deck_list_path, xml_file_path=args.xml_file_path)