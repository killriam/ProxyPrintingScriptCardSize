import os
from pathlib import Path

def find_matching_image(images_dir, card_filename):
    """
    Find a matching image file, with or without the Google Drive ID.
    
    Args:
        images_dir: Directory containing the card images
        card_filename: Filename of the card to find
    
    Returns:
        Path object to the matching file, or None if not found
    """
    # First, check for exact match
    image_path = images_dir / card_filename
    if image_path.exists():
        return image_path
    
    # Extract the base name without any parentheses content
    base_name = card_filename.split('(')[0].strip()
    file_name_without_ext = os.path.splitext(card_filename)[0]
    extension = os.path.splitext(card_filename)[1]
    
    # Get potential card name - remove edition tags like [ELD], version numbers like {281}
    card_name_only = base_name
    for bracket_type in ['[', '{']:
        if bracket_type in card_name_only:
            card_name_only = card_name_only.split(bracket_type)[0].strip()
    
    # Series of increasingly flexible matching strategies
    
    # 1. Try exact base name match with various extensions
    if base_name:
        for ext in ['.png', '.jpg', '.jpeg', extension]:
            potential_path = images_dir / f"{base_name}{ext}"
            if potential_path.exists():
                print(f"Found alternative file: {potential_path} (instead of {card_filename})")
                return potential_path
    
    # 2. Case-insensitive match for file starting with the base name
    base_name_lower = base_name.lower()
    for file_path in images_dir.glob("*.*"):
        if file_path.is_file() and file_path.stem.lower().startswith(base_name_lower):
            print(f"Found case-insensitive match: {file_path} (instead of {card_filename})")
            return file_path
    
    # 3. Search for any file that starts with the same name
    for file_path in images_dir.glob(f"{base_name}*"):
        if file_path.is_file():
            print(f"Found similar file: {file_path} (instead of {card_filename})")
            return file_path
    
    # 4. Look for partial name matches
    for file_path in images_dir.glob("*"):
        if file_path.is_file():
            # Check various matching conditions
            file_stem = file_path.stem.lower()
            if (file_name_without_ext.lower() in file_stem or 
                base_name.lower() in file_stem or
                card_name_only.lower() in file_stem):
                print(f"Found partial match: {file_path} (instead of {card_filename})")
                return file_path
    
    # 5. Try word-based matching for more complex filenames
    # Split the filename into words and look for files containing most of these words
    if ' ' in base_name:
        words = [w.lower() for w in base_name.split() if len(w) > 2]  # Skip short words
        if words:
            best_match = None
            max_matches = 0
            
            for file_path in images_dir.glob("*.*"):
                if not file_path.is_file():
                    continue
                    
                file_stem = file_path.stem.lower()
                matches = sum(1 for word in words if word in file_stem)
                
                # If this file matches more words than our previous best match, use this one
                if matches > max_matches:
                    max_matches = matches
                    best_match = file_path
            
            # Consider a match valid if it contains at least half of the words
            if best_match and max_matches >= len(words) // 2:
                print(f"Found word-based match: {best_match} (instead of {card_filename})")
                return best_match
    
    # 6. Check for related cards (e.g., "Bala Ged Sanctuary" might be related to "Bala Ged Recovery")
    # For DFCs (Double-Faced Cards) or related cards that might have different names
    # Especially useful for backs that might have different names than fronts
    if ' ' in base_name:
        first_word = base_name.split()[0].lower()
        if len(first_word) > 2:  # Only consider meaningful first words
            for file_path in images_dir.glob(f"{first_word}*"):
                if file_path.is_file():
                    print(f"Found related card: {file_path} (instead of {card_filename})")
                    return file_path
    
    print(f"No matching file found for: {card_filename}")
    return None