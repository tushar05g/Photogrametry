
import cv2
import os
from pathlib import Path
import glob

def clean_dataset():
    base_dir = Path("assets/mouse_video_frames")
    output_dir = base_dir / "cleaned"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process both 'above' and 'below' directories
    image_paths = glob.glob(str(base_dir / "above" / "*.png")) + \
                  glob.glob(str(base_dir / "below" / "*.png"))
    
    print(f"🚀 Found {len(image_paths)} images to process.")
    
    # Crop parameters derived from research
    # y=80 to y=605 (Approx 525 height)
    # x=0 to x=800 (Full width)
    Y_START, Y_END = 80, 605
    
    count = 0
    for img_path in image_paths:
        img = cv2.imread(img_path)
        if img is None:
            print(f"⚠️ Failed to read {img_path}")
            continue
            
        # Perform crop
        cropped = img[Y_START:Y_END, :]
        
        # Save to cleaned directory with unique name
        # Prefix with parent folder to avoid collisions since both have frame_01.png
        parent_name = Path(img_path).parent.name
        filename = f"{parent_name}_{Path(img_path).name}"
        save_path = output_dir / filename
        
        cv2.imwrite(str(save_path), cropped)
        count += 1
        if count % 10 == 0:
            print(f"✅ Processed {count} images...")

    print(f"✨ Successfully cleaned {count} images. Saved to {output_dir}")

if __name__ == "__main__":
    clean_dataset()
