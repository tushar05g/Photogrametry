import json
import shutil
import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from storage.provider import StorageProvider

logger = logging.getLogger(__name__)

class LocalStorageProvider(StorageProvider):
    def __init__(self, base_path: str = "/tmp/photogrammetry_storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_local_path(self, remote_path: str) -> Path:
        clean_path = remote_path.lstrip("/")
        return self.base_path / clean_path

    def upload_file(self, path: str, data: Union[bytes, Path, str]) -> str:
        dest = self._get_local_path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        
        if isinstance(data, (str, Path)):
            shutil.copy2(data, dest)
        else:
            with open(dest, "wb") as f:
                f.write(data)
                
        logger.info(f"Local storage: saved to {dest}")
        return path

    def download_file(self, path: str, local_path: Optional[Path] = None) -> Union[bytes, Path]:
        src = self._get_local_path(path)
        if not src.exists():
            raise FileNotFoundError(f"Local file not found: {src}")
            
        if local_path:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, local_path)
            return local_path
        else:
            with open(src, "rb") as f:
                return f.read()

    def list_files(self, path: str) -> List[str]:
        dir_path = self._get_local_path(path)
        if not dir_path.exists():
            return []
        
        # Consistent with S3, return relative keys from base_path
        if dir_path.is_file():
            return [str(dir_path.relative_to(self.base_path))]
            
        return [str(p.relative_to(self.base_path)) for p in dir_path.rglob("*") if p.is_file()]

    def put_json(self, path: str, data: Dict[str, Any]):
        dest = self._get_local_path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "w") as f:
            json.dump(data, f)

    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        src = self._get_local_path(path)
        if not src.exists():
            return None
        with open(src, "r") as f:
            return json.load(f)

    def generate_signed_url(self, path: str, expires_in: int = 3600) -> str:
        return f"file://{self._get_local_path(path)}"

    def delete_file(self, path: str):
        target = self._get_local_path(path)
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
