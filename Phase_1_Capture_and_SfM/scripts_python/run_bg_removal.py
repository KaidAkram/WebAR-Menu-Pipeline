import os
import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm
from rembg import remove

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(base_dir, "processed_data")
    
    IMAGES_DIR = os.path.join(output_dir, "images")
    MASKS_DIR = os.path.join(output_dir, "masks")
    RGBA_DIR = os.path.join(output_dir, "images_rgba")
    
    os.makedirs(MASKS_DIR, exist_ok=True)
    os.makedirs(RGBA_DIR, exist_ok=True)
    
    final_images = sorted([f for f in os.listdir(IMAGES_DIR) if f.endswith('.jpg')])
    
    print(f">> Phase 7/7 -- AI Background Removal on {len(final_images)} frames...")
    
    for fname in tqdm(final_images, desc="  BG removal"):
        img_path = os.path.join(IMAGES_DIR, fname)
        image_pil = Image.open(img_path)

        # Remove background → RGBA with transparent bg
        output_pil = remove(image_pil)

        # Save RGBA
        png_name = os.path.splitext(fname)[0] + ".png"
        output_pil.save(os.path.join(RGBA_DIR, png_name))

        # Extract alpha channel as B&W mask
        output_np = np.array(output_pil)
        if output_np.shape[2] == 4:
            alpha = output_np[:, :, 3]
            cv2.imwrite(os.path.join(MASKS_DIR, png_name), alpha)
            
    print(f"  -> Masks saved to {MASKS_DIR}\nDone.")

if __name__ == "__main__":
    main()
