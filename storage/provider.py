from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

class StorageProvider(ABC):
    @abstractmethod
    def upload_file(self, path: str, data: Union[bytes, Path, str]) -> str:
        """Upload a file (from bytes or path) to storage and return its remote path."""
        pass

    @abstractmethod
    def download_file(self, path: str, local_path: Optional[Path] = None) -> Union[bytes, Path]:
        """Download a file from storage. If local_path is provided, save it there; otherwise return bytes."""
        pass

    @abstractmethod
    def list_files(self, path: str) -> List[str]:
        """List files in storage at a given remote path."""
        pass

    @abstractmethod
    def put_json(self, path: str, data: Dict[str, Any]):
        """Upload JSON data to storage."""
        pass

    @abstractmethod
    def get_json(self, path: str) -> Optional[Dict[str, Any]]:
        """Download JSON data from storage."""
        pass

    @abstractmethod
    def generate_signed_url(self, path: str, expires_in: int = 3600) -> str:
        """Generate a temporary signed URL for a file (if supported)."""
        pass

    @abstractmethod
    def delete_file(self, path: str):
        """Delete a file from storage."""
        pass
