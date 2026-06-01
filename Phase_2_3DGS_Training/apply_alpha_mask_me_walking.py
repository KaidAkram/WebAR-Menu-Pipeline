import os
import sys
from rembg import remove, new_session
from PIL import Image
import io

def process_directory(images_dir):
    print(f"Applying Alpha Mask using rembg (u2net) in: {images_dir}")
    session = new_session('u2net')
    
    files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.jpg', '.jpeg'))]
    if not files:
        print("No .jpg/.jpeg files found to process. They might already be .png")
        return
        
    for filename in files:
        input_path = os.path.join(images_dir, filename)
        png_filename = os.path.splitext(filename)[0] + '.png'
        output_path = os.path.join(images_dir, png_filename)
        
        with open(input_path, 'rb') as i:
            input_data = i.read()
            
        # Remove background (returns RGBA by default as PNG bytes)
        output_data = remove(input_data, session=session)
        
        # Save directly as PNG
        with open(output_path, 'wb') as o:
            o.write(output_data)
        
        print(f"Processed: {filename} -> {png_filename}")
        
        # Delete original jpg
        if input_path != output_path:
            os.remove(input_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python apply_alpha_mask_me_walking.py <images_dir>")
        sys.exit(1)
    process_directory(sys.argv[1])
