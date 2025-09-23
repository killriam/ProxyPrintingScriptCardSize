import os
import win32print
import win32ui
import win32gui
import win32con
from PIL import Image
from pathlib import Path

def crop_and_center_image(image_path, output_path, crop_percentage_top=0.07, crop_percentage_bottom=0.07, crop_percentage_left_right=0.07, canvas_size=(2.5 * 300, 3.5 * 300), dpi=300):
    """
    Crop the image, scale it, and center it on a rectangular canvas.
    """
    # Reduce canvas size by 8% for scaling
    canvas_width, canvas_height = canvas_size
    canvas_width = int(canvas_width * 0.92)
    canvas_height = int(canvas_height * 0.92)

    # Open the image
    img = Image.open(image_path)
    img_width, img_height = img.size

    # Crop the image by the specified percentages
    crop_left_right = int(img_width * crop_percentage_left_right)
    crop_top = int(img_height * crop_percentage_top)
    crop_bottom = int(img_height * crop_percentage_bottom)
    img = img.crop((crop_left_right, crop_top, img_width - crop_left_right, img_height - crop_bottom))

    # Calculate the scaling factor to fit the image within the canvas
    scale_x = canvas_width / img.width
    scale_y = canvas_height / img.height
    scale = min(scale_x, scale_y)

    # Scale the image
    new_width = int(img.width * scale)
    new_height = int(img.height * scale)
    img = img.resize((new_width, new_height), Image.LANCZOS)

    # Create a blank white canvas
    canvas = Image.new("RGB", (int(canvas_width), int(canvas_height)), (255, 255, 255))

    # Center the scaled image on the canvas
    x_offset = (canvas_width - new_width) // 2
    y_offset = (canvas_height - new_height) // 2
    canvas.paste(img, (int(x_offset), int(y_offset)))

    # Save the final image
    canvas.save(output_path, "BMP")
    print(f"Saved cropped and centered image to {output_path}")

def send_image_to_printer(image_path, printer_name, target_size=(2.5 * 300, 3.5 * 300), dpi=300):
    """
    Send image to printer with adjusted size and position compensation.
    """
    printer_dc = None
    mem_dc = None
    hbitmap = None
    old_bitmap = None

    try:
        # Open the printer device context
        printer_dc = win32ui.CreateDC()
        printer_dc.CreatePrinterDC(printer_name)

        # Get printer DPI and physical characteristics
        printer_dpi_x = printer_dc.GetDeviceCaps(win32con.LOGPIXELSX)
        printer_dpi_y = printer_dc.GetDeviceCaps(win32con.LOGPIXELSY)
        
        # Physical offsets from edge of paper to printable area
        physical_offset_x = printer_dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        physical_offset_y = printer_dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
        
        # Calculate target size in printer units with 6% reduction
        card_width_inches = 2.5 * 0.94  # Reduce width by 6%
        card_height_inches = 3.5 * 0.94  # Reduce height by 6%
        
        card_width_du = int(card_width_inches * printer_dpi_x)
        card_height_du = int(card_height_inches * printer_dpi_y)

        # Get physical page dimensions
        page_width_du = printer_dc.GetDeviceCaps(win32con.PHYSICALWIDTH)
        page_height_du = printer_dc.GetDeviceCaps(win32con.PHYSICALHEIGHT)

        # Calculate centering offsets, compensating for physical offsets
        x_offset = ((page_width_du - card_width_du) // 2) - physical_offset_x
        y_offset = ((page_height_du - card_height_du) // 2) - physical_offset_y

        # Load bitmap directly using LoadImage
        hbitmap = win32gui.LoadImage(
            0,
            image_path,
            win32con.IMAGE_BITMAP,
            0,
            0,
            win32con.LR_LOADFROMFILE | win32con.LR_CREATEDIBSECTION
        )

        if not hbitmap:
            raise RuntimeError("Failed to load bitmap")

        # Create a memory DC compatible with the printer DC
        mem_dc = win32gui.CreateCompatibleDC(printer_dc.GetHandleOutput())
        
        # Select bitmap into memory DC
        old_bitmap = win32gui.SelectObject(mem_dc, hbitmap)
        
        # Get source bitmap dimensions
        bitmap_info = win32gui.GetObject(hbitmap)
        
        # Start the print job
        printer_dc.StartDoc(image_path)
        printer_dc.StartPage()

        # Draw the bitmap
        win32gui.StretchBlt(
            printer_dc.GetHandleOutput(),
            x_offset,
            y_offset,
            card_width_du,
            card_height_du,
            mem_dc,
            0,
            0,
            bitmap_info.bmWidth,
            bitmap_info.bmHeight,
            win32con.SRCCOPY
        )

        # End the print job
        printer_dc.EndPage()
        printer_dc.EndDoc()

        print(f"Sent {image_path} to printer {printer_name}")

    except Exception as e:
        print(f"Error sending {image_path} to printer: {e}")
        raise

    finally:
        # Cleanup in reverse order of creation
        try:
            if old_bitmap and mem_dc:
                win32gui.SelectObject(mem_dc, old_bitmap)
            if mem_dc:
                win32gui.DeleteDC(mem_dc)
            if hbitmap:
                win32gui.DeleteObject(hbitmap)
            if printer_dc:
                printer_dc.DeleteDC()
        except Exception as cleanup_error:
            print(f"Cleanup error: {cleanup_error}")

def main():
    # Base directories (use MTG_DIR env var to override)
    script_dir = Path(__file__).resolve().parent
    mtg_dir = Path(os.environ.get("MTG_DIR", script_dir / "mtg"))

    reprint_dir = mtg_dir / "reprint"
    output_folder = mtg_dir / "prints"
    printer_name = os.environ.get("PRINTER_NAME", "tanker")

    # Ensure the output folder exists
    output_folder.mkdir(parents=True, exist_ok=True)

    try:
        # Get all image files from the reprint directory
        if not reprint_dir.exists():
            print(f"Reprint directory not found: {reprint_dir}")
            return

        image_files = [f for f in reprint_dir.iterdir() if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.bmp')]

        if not image_files:
            print(f"No image files found in {reprint_dir}")
            return

        for filepath in image_files:
            image_path = filepath
            output_image_path = output_folder / f"{filepath.stem}.bmp"

            # Process and print the image
            crop_and_center_image(str(image_path), str(output_image_path))
            send_image_to_printer(str(output_image_path), printer_name)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()