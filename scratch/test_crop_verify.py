
import cv2
import numpy as np
import os

img = cv2.imread('assets/mouse_video_frames/all/frame_01.png')
# Crop top 80 and bottom 181
cropped = img[80:600, :]
cv2.imwrite('scratch/test_crop.png', cropped)
print(f"Original: {img.shape}, Cropped: {cropped.shape}")
