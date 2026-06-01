import os
from rembg import remove
from PIL import Image
import io

# 1. Define your folders (Using 'r' to protect against the space in your username)
base_path = r"C:\Users\Akram KAID\Desktop\2CS_project\submission(5)\project"
input_dir = os.path.join(base_path, "images")
output_dir = os.path.join(base_path, "images_masked")

# Create the output folder if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

print("Starting Laser Focus processing...")

# 2. Loop through all 528 images
for filename in os.listdir(input_dir):
    if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
        input_path = os.path.join(input_dir, filename)
        output_path = os.path.join(output_dir, filename)

        # Read the image
        with open(input_path, 'rb') as i:
            input_data = i.read()

        # Remove the background (creates an image with a transparent background)
        output_data = remove(input_data)
        img = Image.open(io.BytesIO(output_data))

        # 3. 3DGS requires JPGs (no transparency), so we paste the food onto a pure black background
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (0, 0, 0))
            # Use the transparency (alpha) channel as a mask to paste perfectly
            background.paste(img, mask=img.split()[3]) 
            background.save(output_path, "JPEG", quality=100)
            print(f"Masked and saved: {filename}")
        else:
            img.save(output_path)
            
print("All 528 frames processed! Ready for 3DGS.")