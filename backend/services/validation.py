"""
🎓 TEACHER'S NOTE — backend/services/validation.py
=====================================================
PURPOSE: This module acts as a "Quality Control Inspector" for all uploaded images.
Before we send photos to an expensive GPU job, we make sure they are worth processing.

WHY VALIDATE?
Gaussian Splatting is very sensitive to input quality. Bad images = bad models. 
Running COLMAP on blurry or duplicate photos wastes GPU time and produces unusable output.

FOUR CHECKS:
1. Count   → Min 10 images needed. COLMAP requires overlap between many viewpoints.
2. Resolution → Each image should be at least 1024x650. Too small = no features to extract.
3. Blur     → Uses Laplacian variance. A blurry image has no sharp edges = low variance.
4. Duplicate → Uses perceptual hashing (pHash). Exact duplicate photos add no new information
              and increase reconstruction time without any benefit.
"""

import io
import hashlib
import requests
import numpy as np
from PIL import Image
import cv2

MIN_IMAGES = 10
MIN_WIDTH = 1024
MIN_HEIGHT = 650
BLUR_THRESHOLD = 10.0  # Below this = blurry. Higher = stricter.


def _load_image_from_url(url: str) -> np.ndarray:
    """
    🎓 Downloads an image from a URL and converts it to a numpy array for OpenCV.
    Numpy array is the universal format for image processing libraries.
    """
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    img_array = np.frombuffer(response.content, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return img


def check_image_count(images: list[str]) -> dict:
    """
    🎓 RULE 1: Minimum image count.
    Why? Structure-from-Motion (COLMAP) works by finding the same physical point in many photos.
    With fewer than 10 images, there isn't enough "overlap" to triangulate 3D positions.
    """
    count = len(images)
    if count < MIN_IMAGES:
        return {
            "passed": False,
            "error": f"Not enough images: {count} uploaded, minimum is {MIN_IMAGES}. "
                     f"For best results, use 20–40 photos taken from all angles."
        }
    return {"passed": True, "count": count}


def check_resolution(img: np.ndarray, url: str) -> dict:
    """
    🎓 RULE 2: Minimum resolution.
    Why? Feature extraction (SIFT in COLMAP) looks for distinct "keypoints" in images.
    A very small image simply doesn't have enough pixels to identify reliable features.
    """
    h, w = img.shape[:2]
    if w < MIN_WIDTH or h < MIN_HEIGHT:
        return {
            "passed": False,
            "warning": f"Low resolution image ({w}x{h}) — minimum is {MIN_WIDTH}x{MIN_HEIGHT}. "
                       f"Image {url.split('/')[-1]} may reduce model quality."
        }
    return {"passed": True}


def check_blur(img: np.ndarray, url: str) -> dict:
    """
    🎓 RULE 3: Blur detection using the Laplacian operator.
    
    HOW IT WORKS:
    - The Laplacian operator is a second-derivative filter. It measures how *quickly* pixel
      values change (i.e., edges).
    - A sharp image has many strong edges → high Laplacian variance.
    - A blurry image has soft, gradual transitions → low Laplacian variance.
    - We measure the .var() (statistical variance) of the result. Below a threshold = blurry.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < BLUR_THRESHOLD:
        return {
            "passed": False,
            "warning": f"Blurry image detected (sharpness score: {laplacian_var:.1f}, "
                       f"minimum: {BLUR_THRESHOLD}). Image {url.split('/')[-1]} may cause reconstruction failures."
        }
    return {"passed": True, "sharpness": laplacian_var}


def _phash(img: np.ndarray) -> str:
    """
    🎓 Perceptual Hash (pHash) — a fingerprint for an image's visual content.
    
    HOW IT WORKS:
    1. Resize image to 32x32 (removes fine detail, keeps shape/structure).
    2. Convert to grayscale.
    3. Apply a Discrete Cosine Transform (DCT) — similar to JPEG compression.
    4. Take the top-left 8x8 of the DCT (this represents low-frequency content = the "shape" of the image).
    5. Compare each value to the mean. Above mean = 1, Below = 0.
    6. Serialize the 64-bit result into a hex string.

    Two images with the same pHash look essentially identical to a human eye.
    """
    resized = cv2.resize(img, (32, 32))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dct = cv2.dct(gray)
    dct_low = dct[:8, :8]
    mean = dct_low.mean()
    bits = (dct_low > mean).flatten().astype(np.uint8)
    # Pack 64 bits into 8 bytes, then hex-encode
    return hashlib.sha256(bits.tobytes()).hexdigest()[:16]


def check_duplicates(images_with_arrays: list[tuple]) -> dict:
    """
    🎓 RULE 4: Duplicate image detection.
    Uses pHash to compare images. Finds exact or near-exact duplicates.
    """
    seen_hashes = {}
    duplicates = []
    for url, img in images_with_arrays:
        h = _phash(img)
        if h in seen_hashes:
            duplicates.append(url.split("/")[-1])
        else:
            seen_hashes[h] = url

    if duplicates:
        return {
            "passed": False,
            "warning": f"Duplicate images detected: {', '.join(duplicates)}. "
                       "Remove duplicates for a faster, cleaner reconstruction."
        }
    return {"passed": True}


def validate_dataset(image_urls: list[str]) -> dict:
    """
    🎓 MAIN ENTRY POINT — runs all validation checks and returns a report.
    
    Returns:
        { "valid": bool, "errors": [...], "warnings": [...] }
    
    "errors" block the job. "warnings" are reported but do not stop reconstruction.
    """
    errors = []
    warnings = []

    # Check 1: Count (fails fast — no need to download images if count is wrong)
    count_result = check_image_count(image_urls)
    if not count_result["passed"]:
        return {"valid": False, "errors": [count_result["error"]], "warnings": []}

    # Download all images for further checks
    images_with_arrays = []
    for url in image_urls:
        try:
            img = _load_image_from_url(url)
            images_with_arrays.append((url, img))
        except Exception as e:
            errors.append(f"Could not download image {url.split('/')[-1]}: {e}")

    if errors:
        return {"valid": False, "errors": errors, "warnings": []}

    # Check 2: Resolution
    for url, img in images_with_arrays:
        result = check_resolution(img, url)
        if not result["passed"]:
            warnings.append(result["warning"])

    # Check 3: Blur
    for url, img in images_with_arrays:
        result = check_blur(img, url)
        if not result["passed"]:
            warnings.append(result["warning"])

    # Check 4: Duplicates
    dup_result = check_duplicates(images_with_arrays)
    if not dup_result["passed"]:
        warnings.append(dup_result["warning"])

    return {
        "valid": True,
        "errors": errors,
        "warnings": warnings,
        "image_count": len(image_urls)
    }
