import scribus, sys

# --- copies setting ---
COPIES = 3  # default
if len(sys.argv) > 1:
    try:
        COPIES = int(sys.argv[1])
    except ValueError:
        print(f"Invalid argument {sys.argv[1]!r}, using default {COPIES}")

INSERT_AFTER_1 = True  # True: insert right after page 1, False: append at end

if not scribus.haveDoc():
    raise SystemExit("No document open.")

try:
    scribus.setRedraw(False)

    # capture items on page 1
    scribus.gotoPage(1)
    items_on_p1 = [t[0] for t in scribus.getPageItems()]  # item names

    for i in range(COPIES):
        if INSERT_AFTER_1:
            insert_at = 2 + i
            scribus.newPage(insert_at)
            scribus.gotoPage(insert_at)
        else:
            scribus.newPage(-1)
            scribus.gotoPage(scribus.pageCount())

        # copy + paste objects
        scribus.gotoPage(1)
        for name in items_on_p1:
            scribus.selectObject(name)
            scribus.copyObject()

        scribus.gotoPage(insert_at if INSERT_AFTER_1 else scribus.pageCount())
        for _ in items_on_p1:
            scribus.pasteObject()

        scribus.messagebarText(f"Duplicated page 1 -> page {scribus.currentPage()} ({i+1}/{COPIES})")




    print(f"Done: duplicated page 1 {COPIES} times.")

finally:
    scribus.setRedraw(True)
    scribus.docChanged(True)
    scribus.saveDoc()
