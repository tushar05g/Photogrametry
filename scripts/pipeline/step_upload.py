import os
import cloudinary
import cloudinary.uploader
import logging

logger = logging.getLogger("worker")

class UploadStep:
    def execute(self, file_path, cloud_name, api_key, api_secret):
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError("No artifact file found to upload.")

        try:
            logger.info(f"📤 Uploading {os.path.basename(file_path)} to Cloudinary...")
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )

            response = cloudinary.uploader.upload(
                file_path,
                resource_type="raw",
                folder="3d_models"
            )

            return response["secure_url"]
        except Exception as e:
            logger.error(f"❌ Upload failed: {e}")
            raise RuntimeError(f"Cloudinary upload failed: {e}")
