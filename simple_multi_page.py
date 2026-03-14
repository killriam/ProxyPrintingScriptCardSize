#!/usr/bin/env python3
"""
A simplified script to create multi-page Scribus documents:
1. Read cards.xml file
2. Copy .sla template
3. Execute copy_slaTemplate.py with card count as parameter
4. Replace image URLs with card-specific ones
"""
import sys
import os
import argparse
import xml.etree.ElementTree as ET
import shutil
import subprocess
import re
import glob
import time
from pathlib import Path

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Create a multi-page Scribus document from an XML file")
    parser.add_argument("xml_file", help="Path to XML file with card information")
    parser.add_argument("--template", "-t", default="scribus_template_proxy.sla", help="Path to template SLA file")
    parser.add_argument("--output-dir", "-o", help="Output directory (default: ready2Print/[deck_name])")
    parser.add_argument("--deck-name", "-d", default=None, help="Override deck name used for image lookup and output filename")
    parser.add_argument("--base-dir", "-b", help="Base directory for the project")
    parser.add_argument("--create-cardback", action="store_true", help="Create cardback SLA file")
    args = parser.parse_args()
    script_dir = Path(__file__).resolve().parent
    base_dir = Path(args.base_dir) if args.base_dir else script_dir
    
    # Load XML file
    try:
        xml_path = Path(args.xml_file)
        if not xml_path.is_absolute():
            xml_path = base_dir / xml_path
            
        if not xml_path.exists():
            print(f"Error: XML file not found: {xml_path}")
            return 1
        
        print(f"Reading XML file: {xml_path}")
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        # Determine deck name from XML filename
        deck_name = xml_path.stem
        if deck_name.startswith("cards_"):
            deck_name = deck_name[6:]  # Remove "cards_" prefix if present
        # Allow caller to override deck name (e.g. to strip date+scope suffix)
        if args.deck_name:
            deck_name = args.deck_name
            
        # Find all cards in the XML
        fronts = root.find("fronts")
        if fronts is None:
            print("Error: No 'fronts' section found in XML file")
            return 1
            
        cards = list(fronts.findall("card"))
        card_count = len(cards)
        print(f"Found {card_count} cards in XML file")
        
        if card_count == 0:
            print("No cards found in XML file")
            return 1
            
        # Determine output directory - always under ready2Print/
        ready2print_dir = base_dir / "ready2Print"
        if args.output_dir:
            output_path = ready2print_dir / args.output_dir
        else:
            output_path = ready2print_dir / deck_name
            
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
            
        # Determine if this is a test XML
        is_test_xml = "mtg_test" in str(xml_path)
        
        # Determine image directories
        mtg_dir = Path(os.environ.get("MTG_DIR", base_dir / "mtg"))
        if is_test_xml:
            image_dir = base_dir / "mtg_test" / "images" / deck_name
        else:
            image_dir = mtg_dir / "images" / deck_name
            
        print(f"Using image directory: {image_dir}")
            
        # Collect card image paths
        card_image_paths = []
        for card in cards:
            # Try to find the card name element
            card_name_elem = card.find("name")
            if card_name_elem is None:
                card_name_elem = card.find("n")  # Try legacy format
                
            if card_name_elem is None:
                print(f"Warning: Card without name tag found, skipping")
                card_image_paths.append(None)
                continue
                
            card_filename = card_name_elem.text
            
            # Find matching image file
            actual_image_path = find_matching_image_file(image_dir, card_filename)
            
            if actual_image_path and os.path.isfile(actual_image_path):
                # Use absolute forward-slash path — avoids Scribus relative-path issues on Windows
                abs_path = str(Path(actual_image_path).resolve()).replace('\\', '/')
                card_image_paths.append(abs_path)
                print(f"Found image for card: {card_filename} -> {abs_path}")
            else:
                print(f"Warning: No image found for card: {card_filename}")
                card_image_paths.append(None)
            
        # Output directory has already been determined above
        
        # Set output file path
        output_file_path = output_path / f"{deck_name}_multi.sla"
        print(f"Output file will be: {output_file_path}")
        
        # Load template file
        template_path = Path(args.template)
        if not template_path.is_absolute():
            template_path = base_dir / template_path
            
        if not template_path.exists():
            print(f"Error: Template file not found: {template_path}")
            return 1
        
        print(f"Using template: {template_path}")
        
        # Create a copy of the template as our output file
        print(f"Copying template to output file...")
        shutil.copy(template_path, output_file_path)
        
        # Now run the copy_slaTemplate.py script with Scribus
        # The script duplicates the first page for each card
        scribus_cmd = os.environ.get("SCRIBUS_CMD", "scribus")
        script_path = base_dir / "copy_slaTemplate.py"
        
        if not script_path.exists():
            print(f"Error: copy_slaTemplate.py not found at {script_path}")
            return 1
        
        # Need to create card_count - 1 copies, since the first page already exists
        copies_to_create = card_count - 1
        
        print(f"Running Scribus to add {copies_to_create} pages to the document...")
        # Format the command as specified, with the SLA file first, then script parameters
        cmd = [scribus_cmd, str(output_file_path), "-g", "-ns", "--python-script", str(script_path), str(copies_to_create)]
        print(f"Executing: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, check=True, text=True, capture_output=True)
            print("Scribus output:")
            print(result.stdout)
            if result.stderr:
                print("Errors:")
                print(result.stderr)
            
                
            if os.path.exists(output_file_path):
                print(f"Successfully created multi-page document with {card_count} pages:")
                print(f"  {output_file_path}")
                
                # Now update the image paths in the SLA file
                print("Updating image paths in the SLA file...")
                if update_image_paths_in_sla(output_file_path, card_image_paths):
                    print("Successfully updated image paths in the SLA file")
                else:
                    print("Warning: Failed to update image paths in the SLA file")
                
                # Create cardback SLA if requested
                if args.create_cardback:
                    print("Creating cardback SLA...")
                    cardback_result = create_cardback_sla(args.xml_file, args.template, args.output_dir, base_dir)
                    if cardback_result != 0:
                        print("Warning: Failed to create cardback SLA")
                
                return 0
            else:
                print(f"Error: Output file not created")
                return 1
                
        except subprocess.CalledProcessError as e:
            print(f"Error running Scribus: {e}")
            print(f"Command: {' '.join(cmd)}")
            print(f"Output: {e.stdout}")
            print(f"Error: {e.stderr}")
            return 1
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

def create_cardback_sla(xml_file, template, output_dir, base_dir):
    """
    Create a multi-page Scribus document for cardbacks using the cardback image from the XML.
    """
    # Load XML file
    try:
        xml_path = Path(xml_file)
        if not xml_path.is_absolute():
            xml_path = base_dir / xml_path
            
        if not xml_path.exists():
            print(f"Error: XML file not found: {xml_path}")
            return 1
        
        print(f"Reading XML file for cardback: {xml_path}")
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        
        # Determine deck name from XML filename
        deck_name = xml_path.stem
        if deck_name.startswith("cards_"):
            deck_name = deck_name[6:]  # Remove "cards_" prefix if present
            
        # Get cardback ID from XML
        cardback_elem = root.find('cardback')
        if cardback_elem is not None:
            cardback_id = cardback_elem.text
            cardback_name = f"{cardback_id}.png"  # Assume .png extension
        else:
            cardback_name = "cardback.png"
            
        # Find all cards in the XML fronts
        fronts = root.find("fronts")
        if fronts is None:
            print("Error: No 'fronts' section found in XML file")
            return 1
            
        cards = list(fronts.findall("card"))
        total_cards = len(cards)
        print(f"Found {total_cards} cards for cardback SLA")
        
        # For cardback, create only 1 page
        card_count = 1
            
        # Determine output directory - always under ready2Print/
        ready2print_dir = base_dir / "ready2Print"
        if output_dir:
            output_path = ready2print_dir / output_dir
        else:
            output_path = ready2print_dir / deck_name
            
        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)
            
        # Determine if this is a test XML
        is_test_xml = "mtg_test" in str(xml_path)
        
        # Determine image directories
        mtg_dir = Path(os.environ.get("MTG_DIR", base_dir / "mtg"))
        if is_test_xml:
            image_dir = base_dir / "mtg_test" / "images" / deck_name
        else:
            image_dir = mtg_dir / "images" / deck_name
            
        print(f"Using image directory for cardback: {image_dir}")
            
        # Find cardback image
        cardback_image_path = find_matching_image_file(image_dir, cardback_name)
        
        # If not found, try fallback names
        if not cardback_image_path:
            fallback_names = ["cardback.png", "cardback.jpg", "Cardback.png", "Cardback.jpg"]
            for name in fallback_names:
                cardback_image_path = find_matching_image_file(image_dir, name)
                if cardback_image_path:
                    print(f"Found cardback image with fallback name: {name}")
                    break
        
        # If still not found, look for files containing the cardback ID
        if not cardback_image_path and cardback_elem is not None:
            pattern = f"*{cardback_id}*.png"
            matching_files = list(Path(image_dir).glob(pattern))
            if matching_files:
                cardback_image_path = matching_files[0]
                print(f"Found cardback image by ID: {matching_files[0].name}")
            else:
                pattern = f"*{cardback_id}*.jpg"
                matching_files = list(Path(image_dir).glob(pattern))
                if matching_files:
                    cardback_image_path = matching_files[0]
                    print(f"Found cardback image by ID: {matching_files[0].name}")
        
        if not cardback_image_path:
            print(f"Error: Cardback image not found: {cardback_name} in {image_dir}")
            return 1
        
        # Compute relative path
        try:
            rel_path = os.path.relpath(cardback_image_path, start=output_path)
            rel_path = rel_path.replace('\\', '/')
            print(f"Using cardback image: {rel_path}")
        except Exception as e:
            print(f"Error computing relative path for cardback: {e}")
            # Use absolute path as fallback
            abs_path = str(cardback_image_path).replace('\\', '/')
            rel_path = abs_path
            print(f"Using absolute path for cardback: {abs_path}")
        
        # All pages use the same cardback image
        card_image_paths = [rel_path] * card_count
        
        # Set output file path
        output_file_path = output_path / f"{deck_name}_cardback.sla"
        print(f"Cardback output file will be: {output_file_path}")
        
        # Load template file
        template_path = Path(template)
        if not template_path.is_absolute():
            template_path = base_dir / template_path
            
        if not template_path.exists():
            print(f"Error: Template file not found: {template_path}")
            return 1
        
        print(f"Using template for cardback: {template_path}")
        
        # Create a copy of the template as our output file
        print("Copying template to cardback output file...")
        shutil.copy(template_path, output_file_path)
        # Ensure the SLA is only a single page (remove any extra pages if present)
        sanitize_sla_keep_first_page(output_file_path)

        # No duplication needed for cardback — template already has one page
        print("Skipping page duplication for cardback (single page document).")
        if os.path.exists(output_file_path):
            print(f"Cardback document ready: {output_file_path}")
            # Now update the image paths in the SLA file
            print("Updating image path in the cardback SLA file...")
            if update_image_paths_in_sla(output_file_path, card_image_paths):
                print("Successfully updated image path in the cardback SLA file")
                return 0
            else:
                print("Warning: Failed to update image paths in the cardback SLA file")
                return 1
        else:
            print("Error: Cardback output file not created")
            return 1
        
    except Exception as e:
        print(f"Error in create_cardback_sla: {e}")
        import traceback
        traceback.print_exc()
        return 1

def find_matching_image_file(image_dir, card_filename):
    """
    Find an image file that matches the card filename, even if it has Google Drive IDs appended.
    
    Returns the actual filename if found, or None if not found.
    """
    image_path = Path(image_dir)
    if not image_path.exists():
        return None
    
    # First try exact match
    exact_path = image_path / card_filename
    if exact_path.exists():
        return exact_path
    
    # Extract base name and extension
    name_without_ext, ext = os.path.splitext(card_filename)
    
    # Look for files that start with the base name and have the same extension
    pattern = f"{glob.escape(name_without_ext)} (*){ext}"
    matching_files = list(image_path.glob(pattern))
    
    if matching_files:
        return matching_files[0]  # Return the first match
    
    # If no match with Google Drive ID pattern, try a more relaxed search
    # Look for any file that starts with the base name
    pattern = f"{glob.escape(name_without_ext)}*{ext}"
    matching_files = list(image_path.glob(pattern))
    
    if matching_files:
        return matching_files[0]  # Return the first match
    
    return None


def sanitize_sla_keep_first_page(sla_file_path):
    """
    Ensure the SLA file contains only the first <PAGE .../> element and set ANZPAGES to 1.
    This protects against accidentally duplicated SLA files.
    """
    try:
        with open(sla_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find all self-closing PAGE tags
        page_pat = re.compile(r'<PAGE\b[^>]*?/>', re.DOTALL)
        pages = list(page_pat.finditer(content))
        if len(pages) <= 1:
            # nothing to do
            return True

        first = content[pages[0].start():pages[0].end()]
        # Build new content: keep everything before first PAGE, insert first PAGE, then keep everything after last PAGE
        new_content = content[:pages[0].start()] + first + content[pages[-1].end():]

        # Force DOCUMENT ANZPAGES="1"
        new_content = re.sub(r'ANZPAGES="\d+"', 'ANZPAGES="1"', new_content)

        with open(sla_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"Sanitized SLA to a single page: {sla_file_path}")
        return True
    except Exception as e:
        print(f"Warning: Failed to sanitize SLA file {sla_file_path}: {e}")
        return False

def check_file_exists(file_path):
    """
    Check if a file exists and print a warning if it doesn't.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if the file exists, False otherwise
    """
    if file_path and os.path.isfile(file_path):
        return True
    print(f"Warning: File not found: {file_path}")
    return False

def update_image_paths_in_sla(sla_file_path, card_image_paths):
    """
    Update the image paths in the SLA file for each page.
    
    Args:
        sla_file_path: Path to the SLA file
        card_image_paths: List of paths to card images, one per page
    """
    try:
        # First, read the entire SLA file
        with open(sla_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Debug: SLA file content length: {len(content)} characters")

        # Find all PAGEOBJECT self-closing blocks
        matches = list(re.finditer(r'<PAGEOBJECT\b[^>]*?/>', content, re.DOTALL))
        print(f"Debug: Found {len(matches)} PAGEOBJECT blocks in SLA")

        # Collect image-like blocks and keep the first image block as a template
        image_blocks = []  # list of (match_index, start, end, block, attrs)
        first_image_block = None
        page_map = {}

        for idx, m in enumerate(matches):
            block = m.group(0)
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', block))

            # determine page index if present
            page_num = None
            if 'Pagenumber' in attrs:
                try:
                    page_num = int(attrs['Pagenumber'])
                except ValueError:
                    page_num = None
            elif 'OwnPage' in attrs:
                try:
                    page_num = int(attrs['OwnPage'])
                except ValueError:
                    page_num = None

            is_image = 'PFILE' in attrs or attrs.get('PTYPE') == '2' or attrs.get('PICART') == '1'

            if is_image:
                image_blocks.append((idx, m.start(), m.end(), block, attrs, page_num))
                if first_image_block is None:
                    first_image_block = (block, attrs)
                if page_num is not None:
                    page_map.setdefault(page_num, []).append((idx, m.start(), m.end(), block, attrs))

        total_pages = len(card_image_paths)
        print(f"Debug: Collected {len(image_blocks)} image-like PAGEOBJECT blocks; mapped pages: {sorted(page_map.keys())}")

        # Decide strategy: prefer explicit page mapping when it looks meaningful
        meaningful_page_nums = {p for (_, _, _, _, _, p) in image_blocks if p is not None}
        use_mapping = False
        if len(meaningful_page_nums) >= max(2, min(total_pages, len(image_blocks) // 2)):
            # enough different page numbers to trust mapping
            use_mapping = True

        replacements = {}  # match_index -> new_block
        changes = False

        if use_mapping:
            # Use existing Pagenumber/OwnPage attributes to assign images
            for (m_idx, start, end, block, attrs, page_num) in image_blocks:
                if page_num is None or not (0 <= page_num < total_pages):
                    continue
                new_path = card_image_paths[page_num]
                if not new_path:
                    continue
                new_block = block
                pfile_m = re.search(r'PFILE="([^"]*)"', new_block)
                if pfile_m:
                    cur = pfile_m.group(1)
                    if cur != new_path:
                        new_block = new_block.replace(f'PFILE="{cur}"', f'PFILE="{new_path}"', 1)
                        changes = True
                        print(f"Debug: Mapped Page {page_num}: Replaced existing PFILE '{cur}' -> '{new_path}' (match {m_idx})")
                else:
                    # insert PFILE into block
                    insert_text = f' PFILE="{new_path}"'
                    insert_match = re.search(r"\s(IRENDER|EMBEDDED|path)=", new_block)
                    if insert_match:
                        idx_ins = insert_match.start(1)
                        new_block = new_block[:idx_ins] + insert_text + new_block[idx_ins:]
                    else:
                        if new_block.endswith('/>'):
                            new_block = new_block[:-2] + insert_text + '/>'
                        else:
                            new_block = new_block[:-1] + insert_text + '>'
                    changes = True
                    print(f"Debug: Mapped Page {page_num}: Inserted PFILE='{new_path}' into image block (match {m_idx})")

                replacements[m_idx] = new_block

        else:
            # Fallback: assign image blocks sequentially (first image block -> page 0, etc.)
            for assign_idx in range(min(total_pages, len(image_blocks))):
                m_idx, start, end, block, attrs, page_num = image_blocks[assign_idx]
                new_path = card_image_paths[assign_idx]
                if not new_path:
                    continue
                new_block = block
                pfile_m = re.search(r'PFILE="([^"]*)"', new_block)
                if pfile_m:
                    cur = pfile_m.group(1)
                    if cur != new_path:
                        new_block = new_block.replace(f'PFILE="{cur}"', f'PFILE="{new_path}"', 1)
                        changes = True
                        print(f"Debug: Sequential assign page {assign_idx}: Replaced existing PFILE '{cur}' -> '{new_path}' (match {m_idx})")
                else:
                    insert_text = f' PFILE="{new_path}"'
                    insert_match = re.search(r"\s(IRENDER|EMBEDDED|path)=", new_block)
                    if insert_match:
                        idx_ins = insert_match.start(1)
                        new_block = new_block[:idx_ins] + insert_text + new_block[idx_ins:]
                    else:
                        if new_block.endswith('/>'):
                            new_block = new_block[:-2] + insert_text + '/>'
                        else:
                            new_block = new_block[:-1] + insert_text + '>'
                    changes = True
                    print(f"Debug: Sequential assign page {assign_idx}: Inserted PFILE='{new_path}' into image block (match {m_idx})")

                replacements[m_idx] = new_block

            # If there are fewer image blocks than pages, clone the template image block for remaining pages
            if first_image_block is not None:
                template_block, template_attrs = first_image_block
                for idx_page in range(len(image_blocks), total_pages):
                    new_path = card_image_paths[idx_page]
                    if not new_path:
                        continue
                    cloned = template_block
                    if 'Pagenumber' in template_attrs:
                        cloned = re.sub(r'Pagenumber="\d+"', f'Pagenumber="{idx_page}"', cloned)
                    elif 'OwnPage' in template_attrs:
                        cloned = re.sub(r'OwnPage="\d+"', f'OwnPage="{idx_page}"', cloned)
                    else:
                        if cloned.endswith('/>'):
                            cloned = cloned[:-2] + f' OwnPage="{idx_page}"/>'
                        else:
                            cloned = cloned[:-1] + f' OwnPage="{idx_page}">'

                    if 'PFILE' in template_attrs:
                        cloned = re.sub(r'PFILE="[^"]*"', f'PFILE="{new_path}"', cloned, count=1)
                    else:
                        insert_match = re.search(r"\s(IRENDER|EMBEDDED|path)=", cloned)
                        insert_text = f' PFILE="{new_path}"'
                        if insert_match:
                            idx2 = insert_match.start(1)
                            cloned = cloned[:idx2] + insert_text + cloned[idx2:]
                        else:
                            if cloned.endswith('/>'):
                                cloned = cloned[:-2] + insert_text + '/>'
                            else:
                                cloned = cloned[:-1] + insert_text + '>'

                    cloned = re.sub(r'ItemID="\d+"', f'ItemID="{int(time.time()*1000) % 1000000000}"', cloned, count=1)
                    # We'll append cloned blocks at the end of the document
                    # store under a synthetic match index beyond existing ones to insert later
                    replacements[f'clone_{idx_page}'] = cloned
                    changes = True
                    print(f"Debug: Cloned template for missing page {idx_page} and set PFILE='{new_path}'")

        # Rebuild file content using replacements
        out_parts = []
        last = 0
        for i, m in enumerate(matches):
            start, end = m.start(), m.end()
            out_parts.append(content[last:start])
            if i in replacements:
                out_parts.append(replacements[i])
            else:
                out_parts.append(m.group(0))
            last = end

        out_parts.append(content[last:])
        new_content = ''.join(out_parts)

        # Insert any cloned blocks before </DOCUMENT>
        for key, cloned in list(replacements.items()):
            if isinstance(key, str) and key.startswith('clone_'):
                new_content = new_content.replace('</DOCUMENT>', f'{cloned}\n    </DOCUMENT>')

        print(f"Debug: Changes made to SLA file: {changes}")

        with open(sla_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"Debug: Updated SLA file written successfully")
        return True
    
    except Exception as e:
        print(f"Error updating image paths in SLA file: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    sys.exit(main())