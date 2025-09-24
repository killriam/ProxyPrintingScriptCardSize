#!/usr/bin/env python3
import os, sys, traceback, tempfile
out_path = os.path.join(tempfile.gettempdir(), 'scribus_printers_abs.txt')
try:
    import scribus
    names = scribus.getPrinterNames()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('OK\n')
        for n in names:
            f.write(n + '\n')
    print('WROTE', out_path)
except Exception as e:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('ERROR\n')
        f.write(str(e) + '\n')
        traceback.print_exc(file=f)
    print('ERROR - wrote', out_path)
sys.exit(0)
