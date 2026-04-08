import os
import logging
import cloudinary
import cloudinary.uploader
import cloudinary.api
import cloudinary.utils
import requests
import json
import tempfile
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from storage.provider import StorageProvider
from backend.config import settings

logger = logging.getLogger(__name__)

class CloudinaryStorageProvider(StorageProvider):
    def __init__(self):
        cloudinary.config(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )

    def get_url(self, path: str) -> str:
        """Get the public URL for a given path."""
        normalized = path.lstrip("/")
        url, _ = cloudinary.utils.cloudinary_url(normalized, secure=True)
        return url

    def _resolve_existing_url(self, path: str) -> str:
        """
        Resolve a valid URL from Cloudinary by probing common resource types.
        """
        normalized = path.lstrip("/")
        for resource_type in ("image", "video", "raw"):
            try:
                resource = cloudinary.api.resource(normalized, resource_type=resource_type)
                secure_url = resource.get("secure_url")
                if secure_url:
                    return secure_url
            except Exception:
                continue
        return self.get_url(normalized)

    def upload_file(self, path: str, data: Union[bytes, Path, str]) -> str:
        """Uploads a file to Cloudinary."""
        try:
            # Handle different data types
            if isinstance(data, bytes):
                # If bytes, we'll use a temporary file or upload directly
                import io
                file_obj = io.BytesIO(data)
                resp = cloudinary.uploader.upload(
                    file_obj,
                    public_id=path,
                    overwrite=True,
                    resource_type="auto",
                    invalidate=True,
                    unique_filename=False,
                    use_filename=True
                )
            else:
                # If path or str
                local_path = str(data)
                resp = cloudinary.uploader.upload(
                    local_path,
                    public_id=path,
                    overwrite=True,
                    resource_type="auto",
                    invalidate=True,
                    unique_filename=False,
                    use_filename=True
                )
            
            logger.info(f"✅ Cloudinary upload success: {path}")
            return resp.get("secure_url")
        except Exception as e:
            logger.error(f"❌ Cloudinary upload failed for {path}: {str(e)}")
            raise

    def download_file(self, path: str, dest_path: Optional[Path] = None) -> Union[bytes, Path]:
        """Download a file from Cloudinary."""
        try:
            url = self._resolve_existing_url(path)
            logger.info(f"📥 Downloading from Cloudinary: {url}")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            if dest_path:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logger.info(f"✅ Saved to: {dest_path}")
                return dest_path
            else:
                return response.content
        except Exception as e:
            logger.error(f"❌ Cloudinary download failed for {path}: {str(e)}")
            raise

    def list_files(self, path: str) -> List[str]:
        """List files in a prefix."""
        try:
            # Cloudinary search API
            prefix = path.rstrip('/')
            resources = cloudinary.api.resources(
                type="upload",
                prefix=prefix,
                max_results=500
            )
            # Cloudinary stores public_id without extension by default unless unique_filename=False
            # But we are passing public_id=path (with extension). 
            return [r["public_id"] for r in resources.get("resources", [])]
        except Exception as e:
            logger.error(f"❌ Cloudinary list failed for prefix {path}: {str(e)}")
            return []

    def put_json(self, path: str, data: Dict[str, Any]):
        json_data = json.dumps(data).encode("utf-8")
        self.upload_file(path, json_data)

    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            content = self.download_file(path)
            if isinstance(content, bytes):
                return json.loads(content.decode("utf-8"))
            return None
        except Exception:
            return None

    def generate_signed_url(self, path: str, expires_in: int = 3600) -> str:
        return self.get_url(path)

    def delete_file(self, path: str):
        try:
            cloudinary.uploader.destroy(path)
        except Exception as e:
            logger.warning(f"Cloudinary delete failed for {path}: {e}")
