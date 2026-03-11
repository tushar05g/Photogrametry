import os
import requests
import io
import logging

logger = logging.getLogger("worker")

class MaskingStep:
    def __init__(self):
        self.session = None
        self._init_session()

    def _init_session(self):
        try:
            # Lazy import: PIL/rembg loaded AFTER install_dependencies() runs
            from rembg import new_session
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            self.session = new_session("isnet-general-use", providers=providers)
            logger.info("✅ Masking engine initialized with GPU/CPU session.")
        except Exception as e:
            logger.warning(f"⚠️ GPU Masking init failed: {e}. Falling back to CPU.")
            self.session = None

    def execute(self, images, output_folder):
        # Lazy imports inside execute() to avoid locking library versions
        from rembg import remove
        from PIL import Image

        os.makedirs(output_folder, exist_ok=True)
        success_count = 0
        
        for i, url in enumerate(images):
            img_bytes = b""
            try:
                img_bytes = requests.get(url, timeout=30).content
                # Use rembg with persistent session
                masked_bytes = remove(img_bytes, session=self.session)
                
                path = os.path.join(output_folder, f"img_{i:04d}.png")
                with open(path, "wb") as f:
                    f.write(masked_bytes)
                success_count += 1
            except Exception as e:
                logger.error(f"❌ Failed image {i}: {e}")
                # FALLBACK: If masking fails, save the original image to keep pipeline alive
                try:
                    if img_bytes:
                        with open(os.path.join(output_folder, f"img_{i:04d}.png"), "wb") as f:
                            f.write(img_bytes)
                        logger.warning(f"⚠️ Falling back to raw image for index {i}")
                        success_count += 1
                except Exception as fe:
                    logger.error(f"❌ Even fallback failed for image {i}: {fe}")

        if success_count == 0:
            raise RuntimeError("All masking attempts failed — no images could be processed.")
        
        logger.info(f"✅ Masking done: {success_count}/{len(images)} images processed.")
        return output_folder
