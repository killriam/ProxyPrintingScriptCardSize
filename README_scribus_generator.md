# Create Scribus Files for MTG Cards

This script generates Scribus (.sla) files for each card in your cards.xml file, using a template Scribus file as a base. The script replaces the image path in the template with the path to each card image from your XML.

## Features

- Creates individual Scribus files for each card defined in your XML file
- Handles multiple copies of cards using the `slots` element in the XML
- Uses a template Scribus file as a base, only replacing the image path
- Organizes output files in a deck-specific directory

## Usage

```
python create_scribus_files.py <xml_file> [options]
```

### Arguments

- `xml_file`: Path to the XML file with card information (e.g., mtg/cards_power9_corrected.xml)

### Options

- `--template`, `-t`: Path to the Scribus template file (default: scribus_template_proxytest1.sla)
- `--output`, `-o`: Output directory for Scribus files (default: [deck_name]_scribus/)
- `--base-dir`, `-b`: Base directory for the project (default: script directory)
- `--print`, `-p`: Automatically print all generated Scribus files (optional flag)

### Examples

```powershell
# Basic usage with default template
python create_scribus_files.py mtg/cards_power9_corrected.xml

# Specify a custom template and output directory
python create_scribus_files.py mtg_test/cards_doctor_who_deck.xml --template my_template.sla --output doctor_who_scribus

# Generate files and prompt to print them
python create_scribus_files.py mtg/cards_power9_corrected.xml --print
```

## XML Format

The script expects XML files in this format:

```xml
<root>
  <fronts>
    <card>
      <name>Card Name (SET-ID).jpg</name>
      <slots>1, 2, 3</slots>
    </card>
    <!-- more cards -->
  </fronts>
</root>
```

Note: The script also supports the legacy format using `<n>` tag instead of `<name>`.

## Environment Variables

- `MTG_DIR`: Base directory for images and output (default: ./mtg)

## Template Requirements

The script looks for an image reference in the Scribus template file with this pattern:
```xml
PFILE="some_image_name.png"
```

This image reference will be replaced with the path to each card image.

## Output

For each card in the XML file, the script creates a Scribus file named:
```
[output_directory]/[card_filename_without_extension]_[slot].sla
```

For example, if your XML has a card with filename "Black Lotus (LEA-1).jpg" and slots "1, 2", the script will create:
- Black Lotus (LEA-1)_1.sla
- Black Lotus (LEA-1)_2.sla