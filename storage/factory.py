import os
import logging
from backend.config import settings
from storage.provider import StorageProvider

# Providers are imported lazily inside the factory to avoid ModuleNotFound errors
# in environments (like Kaggle) where only specific providers are available.

logger = logging.getLogger(__name__)

def get_storage_provider() -> StorageProvider:
    """
    Factory function to get the storage provider based on configuration.
    """
    # Prefer explicit STORAGE_TYPE setting
    storage_type = getattr(settings, "STORAGE_TYPE", "local").lower()
    
    # Overwrite if we are in a Modal worker AND storage_type is 'modal' or explicitly missing
    if (os.environ.get("MODAL_PROJECT_NAME") or os.environ.get("MODAL_WORKER_ID")) and storage_type == "local":
        from storage.modal_provider import ModalStorageProvider
        logger.info("Detected Modal environment, defaulting to ModalStorageProvider")
        return ModalStorageProvider()

    if storage_type == "s3":
        from storage.s3_provider import S3StorageProvider
        logger.info("Using S3StorageProvider")
        return S3StorageProvider()
    elif storage_type == "modal":
        from storage.modal_provider import ModalStorageProvider
        logger.info("Using ModalStorageProvider")
        return ModalStorageProvider()
    elif storage_type == "cloudinary":
        from storage.fallback_provider import FallbackStorageProvider
        from storage.cloudinary_provider import CloudinaryStorageProvider
        
        logger.info("Using CloudinaryStorageProvider with potential fallbacks")
        primary = CloudinaryStorageProvider()
        
        # 🛡️ Only add Modal/Local fallbacks if specifically configured
        secondary = None
        if hasattr(settings, "MODAL_TOKEN_ID") and settings.MODAL_TOKEN_ID:
            try:
                from storage.modal_provider import ModalStorageProvider
                secondary = ModalStorageProvider()
            except Exception as e:
                logger.warning(f"Failed to initialize Modal fallback: {e}")

        # On Kaggle, we might not have LocalStorageProvider file, so wrap it
        tertiary = None
        try:
            from storage.local_provider import LocalStorageProvider
            tertiary = LocalStorageProvider(base_path=settings.STORAGE_BASE_DIR)
        except ImportError:
            logger.info("LocalStorageProvider not available, skipping tertiary fallback")

        if secondary and tertiary:
            return FallbackStorageProvider(primary, secondary, tertiary)
        elif tertiary:
            return FallbackStorageProvider(primary, tertiary)
        return primary
        
    else:
        from storage.local_provider import LocalStorageProvider
        logger.info(f"Using LocalStorageProvider (base_path={settings.STORAGE_BASE_DIR})")
        return LocalStorageProvider(base_path=settings.STORAGE_BASE_DIR)
