import os
import sys
from pathlib import Path
from PIL import Image
import numpy as np

# Create sample images for the test
def create_sample_images():
    # Path to the images directory
    script_dir = Path(__file__).resolve().parent
    mtg_dir = Path(os.environ.get("MTG_DIR", script_dir / "mtg_test"))
    images_dir = mtg_dir / "images"
    reprint_dir = mtg_dir / "reprint"
    
    # Create color gradients for each card
    cards = [
        "Black Lotus (1).jpg",
        "Ancestral Recall (2).png",
        "Time Walk (3).jpg",
        "Mox Sapphire (4).jpg"
    ]
    
    # Create reprint images
    reprint_images = [
        "Volcanic Island.jpg",
        "Underground Sea.png",
        "Bayou.jpg"
    ]
    
    # Make sure directories exist
    images_dir.mkdir(parents=True, exist_ok=True)
    reprint_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate main card images
    colors = [(0, 0, 0), (0, 0, 255), (0, 255, 0), (0, 0, 128)]
    for i, card in enumerate(cards):
        # Create a gradient image
        width, height = 745, 1040  # Magic card proportions
        img_array = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Fill with a gradient using the card's color
        r, g, b = colors[i % len(colors)]
        for y in range(height):
            for x in range(width):
                img_array[y, x, 0] = min(255, r + x // 4)
                img_array[y, x, 1] = min(255, g + y // 5)
                img_array[y, x, 2] = min(255, b + (x + y) // 10)
                
        # Add a "card frame"
        img_array[0:10, :] = [255, 255, 255]  # Top border
        img_array[-10:, :] = [255, 255, 255]  # Bottom border
        img_array[:, 0:10] = [255, 255, 255]  # Left border
        img_array[:, -10:] = [255, 255, 255]  # Right border
        
        # Add card name as text (simplified)
        card_name = card.split('(')[0].strip()
        img_array[20:50, 20:300] = [255, 255, 255]  # Name box
        
        # Save the image
        img = Image.fromarray(img_array)
        img.save(str(images_dir / card))
        print(f"Created sample card: {images_dir / card}")
    
    # Generate reprint card images
    for i, card in enumerate(reprint_images):
        # Create a gradient image
        width, height = 745, 1040  # Magic card proportions
        img_array = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Fill with a gradient using a different color
        r, g, b = [(255, 0, 0), (0, 255, 255), (255, 255, 0)][i % 3]
        for y in range(height):
            for x in range(width):
                img_array[y, x, 0] = min(255, r + y // 4)
                img_array[y, x, 1] = min(255, g + x // 5)
                img_array[y, x, 2] = min(255, b + (x + y) // 10)
                
        # Add a "card frame"
        img_array[0:10, :] = [255, 255, 255]  # Top border
        img_array[-10:, :] = [255, 255, 255]  # Bottom border
        img_array[:, 0:10] = [255, 255, 255]  # Left border
        img_array[:, -10:] = [255, 255, 255]  # Right border
        
        # Save the image
        img = Image.fromarray(img_array)
        img.save(str(reprint_dir / card))
        print(f"Created sample reprint card: {reprint_dir / card}")

# Create a mock printer class to intercept print commands
class MockPrinter:
    def __init__(self, script_name):
        self.script_name = script_name
        self.script_dir = Path(__file__).resolve().parent
        
    def run(self):
        # Set environment variables to use our test folder and mock printer
        os.environ["MTG_DIR"] = str(self.script_dir / "mtg_test")
        os.environ["PRINTER_NAME"] = "MOCK_PRINTER"  # Won't find this printer, will fail gracefully
        
        # Import the script module but patch the send_image_to_printer function
        print(f"\nRunning {self.script_name} with mock printer...")
        try:
            # Import the script module
            script_path = self.script_dir / self.script_name
            import importlib.util
            spec = importlib.util.spec_from_file_location("test_script", str(script_path))
            module = importlib.util.module_from_spec(spec)
            
            # Before executing, replace the printer function with our mock
            def mock_send_image_to_printer(image_path, printer_name, *args, **kwargs):
                print(f"MOCK PRINTER: Would print {image_path} to {printer_name}")
                return True
                
            # Execute the module
            spec.loader.exec_module(module)
            
            # Patch the printer function
            original_printer_func = module.send_image_to_printer
            module.send_image_to_printer = mock_send_image_to_printer
            
            # Call the main function
            print(f"Calling main() function in {self.script_name}...")
            module.main()
            
            # Restore original function
            module.send_image_to_printer = original_printer_func
            
        except Exception as e:
            print(f"Error running script: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # First create sample images
    create_sample_images()
    
    # Ask which script to test
    print("\nWhich script would you like to test?")
    print("1. Print_cards_sm.py (XML-based card printing)")
    print("2. reprint.py (Reprint folder based printing)")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "1":
        MockPrinter("Print_cards_sm.py").run()
    elif choice == "2":
        MockPrinter("reprint.py").run()
    else:
        print("Invalid choice. Please enter 1 or 2.")