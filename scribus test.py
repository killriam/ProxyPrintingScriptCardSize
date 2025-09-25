import sys, os
import scribus

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr); sys.exit(code)

# Usage: scribus -py print_direct.py file.sla -- --printer "PRINTER" --copies 1 --from 1 --to 0
sla = None; printer = None; copies = 1; p_from = 1; p_to = 0

argv = sys.argv[1:]
if not argv: die("Expected: <file.sla>")
sla = argv[0]
if not os.path.isfile(sla): die(f"SLA not found: {sla}")

if "--" in argv:
    i = argv.index("--") + 1
    cli = argv[i:]
    it = iter(cli)
    for k in it:
        if k == "--printer": printer = next(it, None)
        elif k == "--copies": copies = int(next(it, "1"))
        elif k == "--from":   p_from = int(next(it, "1"))
        elif k == "--to":     p_to = int(next(it, "0"))  # 0 => all pages to end

# Open document if not already open
if not scribus.haveDoc():
    if not scribus.openDoc(sla):
        die("Could not open SLA")

# Select printer (optional)
if printer:
    names = scribus.getPrinterNames()
    if printer not in names:
        die(f"Printer '{printer}' not found. Available: {names}")
    scribus.setPrinter(printer)

# If p_to=0, set it to last page
if p_to == 0:
    p_to = scribus.pageCount()

# setPrintOptions(copies, from_page, to_page, use_alt_print_dialog, output_to_file, use_color)
scribus.setPrintOptions(max(1, copies), p_from, p_to, 0, 0, 1)

# This only works when Scribus is running with GUI (no -g)
scribus.printDocument()
print("SUCCESS: print job sent")
