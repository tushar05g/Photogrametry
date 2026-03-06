import cloudinary
import cloudinary.uploader
from app.core.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

# This configures the library with your secret "locker" keys from the .env file
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

def upload_image_to_cloudinary(file_content, job_id: str):
    """
    Takes raw image bytes and sends them to Cloudinary.
    We organize them into a folder named after the job_id.
    """
    result = cloudinary.uploader.upload(
        file_content,
        folder=f"3d_scanner/scans/{job_id}",
        resource_type="image"
    )
    # result is a dictionary containing the 'secure_url' - the public link to the image
    return result.get("secure_url")
