import anyio
import cloudinary
import cloudinary.uploader
from app.core.config import CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET

# Initialize Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

def _sync_upload(file_data, folder_name):
    """The actual blocking call to Cloudinary."""
    return cloudinary.uploader.upload(file_data, folder=folder_name)

async def upload_image_to_cloudinary(file, folder_name="3d_scanner_uploads"):
    """
    Takes a file, uploads it to Cloudinary in a separate thread 
    so it doesn't block the main web server.
    """
    # Use anyio to run the blocking sync call in a thread pool
    response = await anyio.to_thread.run_sync(_sync_upload, file, folder_name)
    return response.get("secure_url")
