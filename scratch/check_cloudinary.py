import os
import cloudinary
import cloudinary.api
from backend.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

job_id = "16dc1228-1cc6-4eda-898e-74ff23d1a049"
prefix = f"jobs/{job_id}/input/preprocessed"

print(f"Listing files with prefix: {prefix}")
try:
    # Try with default (image)
    res_img = cloudinary.api.resources(type="upload", prefix=prefix, max_results=500)
    print(f"Images found: {[r['public_id'] for r in res_img.get('resources', [])]}")
    
    # Try with raw
    res_raw = cloudinary.api.resources(type="upload", prefix=prefix, resource_type="raw", max_results=500)
    print(f"Raw found: {[r['public_id'] for r in res_raw.get('resources', [])]}")
except Exception as e:
    print(f"Error: {e}")
