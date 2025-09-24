#!/usr/bin/env python3
import os
import traceback
out_path = os.path.join(os.getcwd(), 'scribus_printers_out.txt')
try:
    import scribus
    names = scribus.getPrinterNames()
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('OK\n')
        for n in names:
            f.write(n + '\n')
    # also print to stdout if available
    try:
        print('WROTE', out_path)
    except Exception:
        pass
except Exception as e:
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write('ERROR\n')
        f.write(str(e) + '\n')
        traceback.print_exc(file=f)
    try:
        print('ERROR - wrote', out_path)
    except Exception:
        pass
sys.exit(0)
