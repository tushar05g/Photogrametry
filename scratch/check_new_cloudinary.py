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

job_id = "f49ebaeb-fde2-4341-ab0a-30a034095fef"
prefix = f"jobs/{job_id}/input/preprocessed"

print(f"Listing files with prefix: {prefix}")
try:
    for rt in ["image", "raw", "video"]:
        res = cloudinary.api.resources(type="upload", prefix=prefix, resource_type=rt, max_results=500)
        pids = [r['public_id'] for r in res.get('resources', [])]
        print(f"{rt} found: {pids}")
except Exception as e:
    print(f"Error: {e}")
