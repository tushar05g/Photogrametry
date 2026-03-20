"""
Masking Step - Image download with quality validation
"""

import os
import requests
import logging
from PIL import Image
import io

logger = logging.getLogger(__name__)

class MaskingStep:
    def execute(self, images, output_folder):
        """Download and validate images."""
        os.makedirs(output_folder, exist_ok=True)
        
        valid_images = []
        
        for i, url in enumerate(images):
            try:
                img_data = requests.get(url, timeout=30).content
                path = os.path.join(output_folder, f"img_{i:04d}.jpg")
                
                # Validate image quality
                try:
                    img = Image.open(io.BytesIO(img_data))
                    width, height = img.size
                    
                    # Minimum resolution check
                    if width < 640 or height < 480:
                        logger.warning(f"Image {i+1} is too small: {width}x{height}")
                        continue
                    
                    # Aspect ratio check
                    aspect = width / height
                    if aspect < 0.5 or aspect > 2.0:
                        logger.warning(f"Image {i+1} has extreme aspect ratio: {aspect:.2f}")
                        continue
                    
                    # Save valid image
                    with open(path, "wb") as f:
                        f.write(img_data)
                    valid_images.append(path)
                    logger.info(f"Downloaded valid image {i+1}/{len(images)} ({width}x{height})")
                    
                except Exception as e:
                    logger.warning(f"Invalid image {i+1}: {e}")
                    continue
                    
            except Exception as e:
                logger.error(f"Failed to download image {i+1}: {e}")
                continue
        
        if len(valid_images) < 8:
            logger.warning(f"Only {len(valid_images)} valid images. For best results, use 20+ photos from different angles.")
        
        if len(valid_images) < 3:
            raise RuntimeError(f"Too few valid images ({len(valid_images)}). Need at least 3 good photos.")
        
        logger.info(f"Successfully downloaded {len(valid_images)} valid images")
        return output_folder
