import cv2
import pytesseract
from matplotlib import pyplot as plt

# Load image
image = cv2.imread('chart.png')

# Preprocess (you may need to adjust this based on chart colors)
gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
_, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY_INV)

# Run OCR
data = pytesseract.image_to_string(thresh)
print(data)
