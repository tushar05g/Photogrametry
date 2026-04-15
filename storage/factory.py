import os
import logging
from backend.config import settings
from storage.provider import StorageProvider
from storage.local_provider import LocalStorageProvider
from storage.s3_provider import S3StorageProvider
from storage.modal_provider import ModalStorageProvider
from storage.cloudinary_provider import CloudinaryStorageProvider

logger = logging.getLogger(__name__)

def get_storage_provider() -> StorageProvider:
    """
    Factory function to get the storage provider based on configuration.
    """
    # Prefer explicit STORAGE_TYPE setting
    storage_type = getattr(settings, "STORAGE_TYPE", "local").lower()
    
    # Overwrite if we are in a Modal worker AND storage_type is 'modal' or explicitly missing
    # Otherwise, prefer the explicit STORAGE_TYPE (e.g., 'cloudinary')
    if (os.environ.get("MODAL_PROJECT_NAME") or os.environ.get("MODAL_WORKER_ID")) and storage_type == "local":
        logger.info("Detected Modal environment without explicit Cloudinary/S3 config, defaulting to ModalStorageProvider")
        return ModalStorageProvider()

    if storage_type == "s3":
        logger.info("Using S3StorageProvider")
        return S3StorageProvider()
    elif storage_type == "modal":
        logger.info("Using ModalStorageProvider")
        return ModalStorageProvider()
    elif storage_type == "cloudinary":
        from storage.fallback_provider import FallbackStorageProvider
        logger.info("Using CloudinaryStorageProvider with Modal fallback + Local tertiary")
        primary = CloudinaryStorageProvider()
        secondary = ModalStorageProvider()
        tertiary = LocalStorageProvider(base_path=settings.STORAGE_BASE_DIR)  # Local fallback
        return FallbackStorageProvider(primary, secondary, tertiary)
    else:
        logger.info(f"Using LocalStorageProvider (base_path={settings.STORAGE_BASE_DIR})")
        return LocalStorageProvider(base_path=settings.STORAGE_BASE_DIR)
