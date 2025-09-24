# Magic Card Printing Script

This script allows you to print Magic: The Gathering cards from a decklist or XML file.

## Features

- Print Magic cards from a decklist or XML file
- Download card images from Scryfall
- Create deck-specific subfolders
- Crop and center images for printing
- Support for custom images directory

## Usage

```bash
# Print from a decklist
python Print_cards_sm.py -d path/to/decklist.txt

# Print from an XML file
python Print_cards_sm.py -x path/to/cards.xml

# Specify a custom images directory
python Print_cards_sm.py -x path/to/cards.xml -i path/to/images

# Download cards without printing
python Print_cards_sm.py -x path/to/cards.xml --no-print

# Use existing images without downloading any
python Print_cards_sm.py -x path/to/cards.xml --no-download

# Combine options
python Print_cards_sm.py -x path/to/cards.xml -i path/to/images --no-print --no-download
```

## File Formats

### Decklist Format

Each line should follow this format:
```
1x Card Name (SET) CollectorNumber
```

Example:
```
1x Black Lotus (LEA) 1
2x Sol Ring (C21) 263
```

### XML Format

```xml
<order>
    <details>
        <quantity>100</quantity>
        <bracket>108</bracket>
        <stock>(S33) Superior Smooth</stock>
        <foil>false</foil>
    </details>
    <fronts>
        <card>
            <id>1Ji8G1nvAsiATvifYoUoD_HkYz9AA9vxF</id>
            <slots>0</slots>
            <n>Reality Strobe.png</n>
            <query>reality strobe</query>
        </card>
        <!-- More cards -->
    </fronts>
    <!-- Optional backs section -->
    <backs>
        <!-- Card backs if different -->
    </backs>
    <cardback>1-P6ig8blzZBEmB6Mq1fzBPM9xyhngH3F</cardback>
</order>
```

Note: Both `<name>` and `<n>` tags are supported for backwards compatibility.

## Environment Variables

- `MTG_DIR`: Base directory for images and output (default: ./mtg)
- `PRINTER_NAME`: Name of the printer to use (default: tanker)

## Latest Fixes

- The script now properly checks if images already exist before downloading
- Added custom images directory support with `-i` flag
- Fixed image path handling for files with spaces
- Added `--no-print` option to download cards without printing
- Added `--no-download` option to use existing images without downloading
- Fixed path handling for files with spaces in names