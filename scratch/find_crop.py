
import cv2
import numpy as np
import glob
import os

def find_crop_box(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return None
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Threshold to find non-white parts
    # White is 255, so we look for things < 240
    _, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    
    # Get bounding box of all non-white parts
    # Or just the largest one if there's noise
    # Let's combine all contours to find the overall ROI
    all_pts = np.concatenate(contours)
    x, y, w, h = cv2.boundingRect(all_pts)
    
    return (x, y, w, h)

if __name__ == "__main__":
    test_img = "assets/mouse_video_frames/all/frame_01.png"
    box = find_crop_box(test_img)
    print(f"Crop Box (x,y,w,h): {box}")
    
    # Check dimensions of the example
    img = cv2.imread(test_img)
    print(f"Original shape: {img.shape}")
