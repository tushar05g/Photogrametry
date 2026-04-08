import logging
from typing import Optional, List, Dict, Any, Union
from pathlib import Path
from storage.provider import StorageProvider

logger = logging.getLogger(__name__)

class FallbackStorageProvider(StorageProvider):
    def _normalize_path(self, path: str) -> str:
        return str(path).lstrip("/")

    def __init__(self, primary: StorageProvider, secondary: StorageProvider):
        self.primary = primary
        self.secondary = secondary

    def _path_exists(self, provider: StorageProvider, path: str) -> bool:
        """
        Probe existence in a provider without hard-failing.
        """
        try:
            direct = provider.list_files(path)
            if any(p == path for p in direct):
                return True

            parent_prefix = str(Path(path).parent).rstrip("/") + "/"
            parent_files = provider.list_files(parent_prefix)
            return any(p == path for p in parent_files)
        except Exception:
            return False

    def get_url(self, path: str) -> str:
        path = self._normalize_path(path)
        # Resolve URL from whichever provider currently holds the asset.
        if self._path_exists(self.primary, path):
            return self.primary.get_url(path)
        if self._path_exists(self.secondary, path):
            return self.secondary.get_url(path)

        # If neither provider confirms presence, keep best-effort behavior.
        try:
            return self.primary.get_url(path)
        except Exception:
            return self.secondary.get_url(path)

    def upload_file(self, path: str, data: Union[bytes, Path, str]) -> str:
        path = self._normalize_path(path)
        try:
            primary_result = self.primary.upload_file(path, data)
            # Best-effort replication to secondary so reads can fall back seamlessly.
            try:
                self.secondary.upload_file(path, data)
            except Exception as mirror_err:
                logger.debug(f"Secondary mirror skipped for {path}: {mirror_err}")
            return primary_result
        except Exception as e:
            logger.warning(f"Primary storage failed, falling back to secondary: {e}")
            return self.secondary.upload_file(path, data)

    def download_file(self, path: str, local_path: Optional[Path] = None) -> Union[bytes, Path]:
        path = self._normalize_path(path)
        try:
            return self.primary.download_file(path, local_path)
        except Exception:
            logger.debug(f"Primary download failed for {path}, trying secondary")
            return self.secondary.download_file(path, local_path)

    def list_files(self, path: str) -> List[str]:
        # Merge results or try primary then secondary
        path = self._normalize_path(path)
        files = self.primary.list_files(path)
        if not files:
            files = self.secondary.list_files(path)
        normalized: List[str] = []
        seen = set()
        for f in files:
            key = self._normalize_path(f)
            if key and key not in seen:
                normalized.append(key)
                seen.add(key)
        return normalized

    def delete_file(self, path: str):
        path = self._normalize_path(path)
        self.primary.delete_file(path)
        self.secondary.delete_file(path)

    def put_json(self, path: str, data: Dict[str, Any]):
        try:
            self.primary.put_json(path, data)
        except Exception:
            self.secondary.put_json(path, data)

    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        res = self.primary.get_json(path)
        if res is None:
            res = self.secondary.get_json(path)
        return res

    def generate_signed_url(self, path: str, expires_in: int = 3600) -> str:
        try:
            return self.primary.generate_signed_url(path, expires_in)
        except Exception:
            return self.secondary.generate_signed_url(path, expires_in)
