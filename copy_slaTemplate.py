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
        # For robustness: copy each object from page 1 and paste it immediately into the
        # destination page. Copying all objects first and then pasting repeatedly can
        # leave only the last-copied object in the clipboard and result in missing
        # or duplicated objects on duplicated pages.
        dest_page = insert_at if INSERT_AFTER_1 else scribus.pageCount()
        for name in items_on_p1:
            # ensure we're copying the object from the original page
            scribus.gotoPage(1)
            try:
                scribus.deselectAll()
            except Exception:
                # some versions of the API may not have deselectAll; ignore if not present
                pass
            scribus.selectObject(name)
            scribus.copyObject()

            # Paste once on the destination page
            scribus.gotoPage(dest_page)
            scribus.pasteObject()

        scribus.messagebarText(f"Duplicated page 1 -> page {scribus.currentPage()} ({i+1}/{COPIES})")




    print(f"Done: duplicated page 1 {COPIES} times.")

finally:
    scribus.setRedraw(True)
    scribus.docChanged(True)
    scribus.saveDoc()
