import json
import shutil
import logging
import os
import io
import modal
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from storage.provider import StorageProvider
from backend.config import settings

logger = logging.getLogger(__name__)

class ModalStorageProvider(StorageProvider):
    def __init__(self, mount_path: str = "/mnt/storage"):
        """
        In Modal workers, volumes are mounted to a specific path.
        If running locally, we use remote volume access via Modal Client.
        """
        # Detection
        self.is_inside_modal = os.environ.get("MODAL_ENVIRONMENT") is not None or os.environ.get("MODAL_IS_REMOTE") == "1"
        self.mount_path = Path(mount_path)
        self.volume_name = settings.STORAGE_BASE_DIR or "morphic-scan-data"
        
        if self.is_inside_modal:
            logger.info(f"ModalStorageProvider: Inside Modal. Using mount {self.mount_path}")
            self.mount_path.mkdir(parents=True, exist_ok=True)
        else:
            logger.info(f"ModalStorageProvider: Remote mode. Using volume {self.volume_name}")
            try:
                self.volume = modal.Volume.from_name(self.volume_name)
            except Exception as e:
                logger.error(f"Failed to find Modal volume {self.volume_name}. Ensure it is created.")
                raise e

    def _get_volume_path(self, remote_path: str) -> Path:
        clean_path = remote_path.lstrip("/")
        return self.mount_path / clean_path

    def upload_file(self, path: str, data: Union[bytes, Path, str]) -> str:
        if self.is_inside_modal:
            dest = self._get_volume_path(path)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(data, (str, Path)):
                shutil.copy2(data, dest)
            else:
                with open(dest, "wb") as f:
                    f.write(data)
        else:
            # Snapshot data before opening the batch context
            if isinstance(data, (str, Path)):
                file_obj = open(data, "rb")
                close_after = True
            else:
                file_obj = io.BytesIO(data)
                close_after = False
            try:
                with self.volume.batch_upload(force=True) as batch:
                    batch.put_file(file_obj, path)
            finally:
                if close_after:
                    file_obj.close()

        logger.info(f"Modal storage: uploaded {path}")
        return path

    async def upload_file_async(self, path: str, data: Union[bytes, Path, str]) -> str:
        """Non-blocking version for use in FastAPI async endpoints."""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.upload_file, path, data)

    def download_file(self, path: str, local_path: Optional[Path] = None) -> Union[bytes, Path]:
        if self.is_inside_modal:
            src = self._get_volume_path(path)
            if not src.exists():
                raise FileNotFoundError(f"Modal file not found: {src}")
            if local_path:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, local_path)
                return local_path
            else:
                with open(src, "rb") as f:
                    return f.read()
        else:
            # Remote download
            buffer = io.BytesIO()
            for chunk in self.volume.read_file(path):
                buffer.write(chunk)
            content = buffer.getvalue()
            
            if local_path:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "wb") as f:
                    f.write(content)
                return local_path
            return content

    def list_files(self, path: str) -> List[str]:
        if self.is_inside_modal:
            dir_path = self._get_volume_path(path)
            if not dir_path.exists(): return []
            if dir_path.is_file(): return [str(dir_path.relative_to(self.mount_path))]
            return [str(p.relative_to(self.mount_path)) for p in dir_path.rglob("*") if p.is_file()]
        else:
            # Remote list
            files = []
            for entry in self.volume.listdir(path, recursive=True):
                if entry.type == modal.volume.FileEntryType.FILE:
                    files.append(entry.path)
            return files

    def put_json(self, path: str, data: Dict[str, Any]):
        content = json.dumps(data).encode("utf-8")
        self.upload_file(path, content)

    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        try:
            content = self.download_file(path)
            return json.loads(content)
        except Exception:
            return None

    def generate_signed_url(self, path: str, expires_in: int = 3600) -> str:
        return f"modal://{path}"

    def delete_file(self, path: str):
        if self.is_inside_modal:
            target = self._get_volume_path(path)
            if target.exists():
                if target.is_dir(): shutil.rmtree(target)
                else: target.unlink()
        else:
            # Remote delete not directly in Volume API as single call, but we can use list_files then remove
            # Actually, Volume API has delete_file()
            self.volume.remove(path, recursive=True)
