import os
import cloudinary
import cloudinary.uploader
import logging

logger = logging.getLogger("worker")

class UploadStep:
    def execute(self, file_path, cloud_name, api_key, api_secret):
        if not file_path or not os.path.exists(file_path):
            raise FileNotFoundError("No artifact file found to upload.")

        import time
        max_retries = 3
        base_delay = 5

        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"📤 Uploading {os.path.basename(file_path)} (Attempt {attempt}/{max_retries})...")
                cloudinary.config(
                    cloud_name=cloud_name,
                    api_key=api_key,
                    api_secret=api_secret
                )

                response = cloudinary.uploader.upload(
                    file_path,
                    resource_type="raw",
                    folder="3d_models",
                    use_filename=True,
                    unique_filename=True,
                    timeout=600
                )

                url = response["secure_url"]
                logger.info(f"✅ Upload successful: {url}")
                return url
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"❌ Upload failed after {max_retries} attempts: {e}")
                    raise RuntimeError(f"Cloudinary upload failed: {e}")
                
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(f"⚠️ Upload failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
