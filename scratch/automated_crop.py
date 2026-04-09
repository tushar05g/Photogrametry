
import cv2
import numpy as np

img = cv2.imread('assets/mouse_video_frames/all/frame_01.png')
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Threshold to find white areas (header/footer)
# White is > 240
_, thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY)

# Invert to get non-white areas
non_white = cv2.bitwise_not(thresh)

# Find rows that are not entirely white
# Actually, just find the first and last row with significant non-white pixels
rows = np.any(non_white > 0, axis=1)
cols = np.any(non_white > 0, axis=0)

ymin, ymax = np.where(rows)[0][[0, -1]]
xmin, xmax = np.where(cols)[0][[0, -1]]

print(f"Detected Crop Box: y={ymin}:{ymax}, x={xmin}:{xmax}")

# Create the cropped image
cropped = img[ymin:ymax, xmin:xmax]
cv2.imwrite('scratch/detected_crop.png', cropped)
print(f"Final shape: {cropped.shape}")
