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
        # 🏁 v10.1.0: Prevent double extensions for image/video
        if normalized.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov')):
            public_id = str(Path(normalized).with_suffix(''))
            url, _ = cloudinary.utils.cloudinary_url(public_id, secure=True)
            # Cloudinary might need the format specified if stripped from PID
            fmt = Path(normalized).suffix.lstrip('.')
            if not url.lower().endswith('.' + fmt.lower()):
                url += '.' + fmt
            return url
        
        url, _ = cloudinary.utils.cloudinary_url(normalized, secure=True)
        return url

    def _resolve_existing_url(self, path: str) -> str:
        """
        Resolve a valid URL from Cloudinary by probing common resource types.
        """
        normalized = path.lstrip("/")
        # 🏁 v10.3.2: Strip extension for API probing if image/video
        probe_id = normalized
        if normalized.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov')):
            probe_id = str(Path(normalized).with_suffix(''))

        for resource_type in ("image", "video", "raw"):
            try:
                resource = cloudinary.api.resource(probe_id, resource_type=resource_type)
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
                
                # 🏁 v11.1.0: Better extension handling
                public_id = path
                resource_type = "auto"
                
                # Strip extension for image/video resource types in Cloudinary
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov')):
                    public_id = str(Path(path).with_suffix(''))
                elif path.lower().endswith(('.ply', '.obj', '.zip', '.glb', '.splat')):
                    resource_type = "raw"

                resp = cloudinary.uploader.upload(
                    file_obj,
                    public_id=public_id,
                    overwrite=True,
                    resource_type=resource_type,
                    invalidate=True,
                    unique_filename=False,
                    use_filename=True
                )
            else:
                # If path or str
                local_path = str(data)
                
                # 🏁 v11.1.0: Consistent public_id and resource_type mapping
                public_id = path
                resource_type = "auto"
                
                if path.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov')):
                    public_id = str(Path(path).with_suffix(''))
                elif path.lower().endswith(('.ply', '.obj', '.zip', '.glb', '.splat')):
                    resource_type = "raw"

                resp = cloudinary.uploader.upload(
                    local_path,
                    public_id=public_id,
                    overwrite=True,
                    resource_type=resource_type,
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
            # 🏁 v10.3.3: Use get_url directly if extension is known to bypass API-probing (indexing lag)
            if path.lower().endswith(('.png', '.jpg', '.jpeg', '.mp4', '.mov', '.zip', '.glb', '.splat')):
                url = self.get_url(path)
            else:
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
        """List files in a prefix by looping over resource types for immediate consistency."""
        try:
            prefix = path.rstrip('/')
            all_files = []
            
            # Loop over all possible resource types to avoid missing files misclassified by Cloudinary.
            # This is more immediately consistent than the Search API.
            for resource_type in ["image", "raw", "video"]:
                try:
                    resources = cloudinary.api.resources(
                        type="upload",
                        prefix=prefix,
                        resource_type=resource_type,
                        max_results=500
                    )
                    for r in resources.get("resources", []):
                        pid = r["public_id"]
                        fmt = r.get("format")
                        
                        # Reconstruct extension if missing in public_id (v10.3.1: Support both image and video)
                        if fmt and resource_type in ("image", "video") and not pid.lower().endswith("." + fmt.lower()):
                            pid += "." + fmt
                        all_files.append(pid)
                except Exception as e:
                    logger.debug(f"ℹ️ No {resource_type} resources found for {prefix}: {e}")
                    continue
                    
            return list(set(all_files)) # Unique results
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
