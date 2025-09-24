#!/usr/bin/env python3
import os, sys, traceback, tempfile, time
out_path = os.path.join(tempfile.gettempdir(), 'scribus_print_debug.txt')
try:
    import scribus
    with open(out_path, 'w', encoding='utf-8') as f:
        def log(*args):
            f.write(' '.join(str(a) for a in args) + '\n')
            f.flush()
        log('scribus module loaded')
        try:
            names = scribus.getPrinterNames()
            log('available_printers_count:', len(names))
            for n in names:
                log('PRINTER:', n)
        except Exception as e:
            log('error getting printer names:', e)
            traceback.print_exc(file=f)
        try:
            target = os.environ.get('SCRIBUS_TARGET_PRINTER')
            log('env SCRIBUS_TARGET_PRINTER=', target)
        except Exception:
            pass
        try:
            if not scribus.haveDoc():
                log('haveDoc: False')
            else:
                log('haveDoc: True')
                try:
                    docname = scribus.getDocName()
                    log('docname:', docname)
                except Exception:
                    pass
                # Try to pick a printer similar to earlier helper
                def pick_printer():
                    names = scribus.getPrinterNames()
                    if not names:
                        return None
                    if target and target in names:
                        return target
                    if target and target not in names:
                        log("Requested printer not found, falling back to first available")
                    return names[0]
                printer = pick_printer()
                log('chosen printer:', printer)
                if printer:
                    try:
                        scribus.setPrinter(printer)
                        log('setPrinter called')
                    except Exception as e:
                        log('setPrinter error:', e)
                        traceback.print_exc(file=f)
                    try:
                        scribus.printDocument()
                        log('printDocument called')
                    except Exception as e:
                        log('printDocument error:', e)
                        traceback.print_exc(file=f)
                else:
                    log('no printer to choose')
        except Exception as e:
            log('error during printing attempt:', e)
            traceback.print_exc(file=f)
    # keep file open briefly to ensure flush
    time.sleep(0.2)
    print('WROTE', out_path)
except Exception as e:
    # if scribus module not available or other fatal error, write out error info
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('FATAL ERROR\n')
            f.write(str(e) + '\n')
            traceback.print_exc(file=f)
    except Exception:
        pass
    print('ERROR writing debug file:', e)
    sys.exit(1)
sys.exit(0)
