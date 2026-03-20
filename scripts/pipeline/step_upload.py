"""
Upload Step - Upload GLB to Cloudinary
"""

import os
import cloudinary
import logging
import cloudinary.uploader

logger = logging.getLogger(__name__)

class UploadStep:
    def execute(self, glb_path):
        """Upload GLB file to Cloudinary."""
        if not os.path.exists(glb_path):
            raise FileNotFoundError(f"GLB file not found: {glb_path}")
        
        try:
            # Configure Cloudinary from environment
            cloud_name = os.getenv("CLOUDINARY_CLOUD_NAME")
            api_key = os.getenv("CLOUDINARY_API_KEY")
            api_secret = os.getenv("CLOUDINARY_API_SECRET")
            
            if not all([cloud_name, api_key, api_secret]):
                raise ValueError("Cloudinary credentials not found in environment variables")
            
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            
            logger.info(f"Uploading {os.path.basename(glb_path)}...")
            
            response = cloudinary.uploader.upload(
                glb_path,
                resource_type="raw",
                folder="3d_models"
            )
            
            return response["secure_url"]
            
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise
