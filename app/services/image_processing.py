import cv2
import numpy as np
import requests
import io
from PIL import Image

# 🎓 TEACHER'S NOTE:
# This service uses OpenCV (Open Computer Vision) to "see" the coin.
# Finding a coin is called "Circle Detection". 
# We use a mathematical trick called the "Hough Circle Transform".

def detect_coin_diameter(image_url: str):
    """
    Downloads an image from a URL and finds the diameter of the largest 
    circular object (our coin) in pixels.
    """
    # 1. Download the image from Cloudinary
    response = requests.get(image_url)
    img_array = np.frombuffer(response.content, np.uint8)
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        return None

    # 2. Pre-processing (Making it easier for the computer to see)
    # Convert to Grayscale (Black and White) because color doesn't matter for shapes
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Blur the image to remove "noise" (tiny dots or dust)
    gray = cv2.medianBlur(gray, 5)

    # 3. Hough Circle Transform 
    # This is the "Magic" part. It looks for patterns of pixels that form a circle.
    circles = cv2.HoughCircles(
        gray, 
        cv2.HOUGH_GRADIENT, 
        dp=1, 
        minDist=100,      # Minimum distance between two circles
        param1=50,       # Canny edge detector threshold
        param2=30,       # Accuracy threshold (lower = more circles found, but more "fake" ones)
        minRadius=20,    # Smallest a coin can be in pixels
        maxRadius=500    # Largest a coin can be in pixels
    )

    if circles is not None:
        # Convert the coordinates to integers
        circles = np.uint16(np.around(circles))
        
        # We assume the largest circle found is our coin!
        # circles[0][0] is [x, y, radius]
        largest_circle = max(circles[0, :], key=lambda c: c[2])
        radius = largest_circle[2]
        diameter = radius * 2
        
        return float(diameter)
    
    return None

def calculate_pixels_to_cm(diameter_px: float, real_diameter_cm: float = 2.5):
    """
    Calculates how many pixels represent 1 centimeter.
    Default: A standard coin is approx 2.5cm.
    """
    if not diameter_px:
        return None
    
    # Ratio: pixels / centimeters
    return diameter_px / real_diameter_cm
