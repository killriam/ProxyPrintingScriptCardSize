#!/usr/bin/env python3
import sys
try:
    import scribus
    names = scribus.getPrinterNames()
    print('Scribus printer names:')
    for n in names:
        print('-', n)
    if not names:
        print('(no printers returned)')
except Exception as e:
    print('ERROR while listing printers:', e)
    try:
        import traceback
        traceback.print_exc()
    except Exception:
        pass
sys.exit(0)
