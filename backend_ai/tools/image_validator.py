from PIL import Image
import io
import cv2
import numpy as np

MIN_WIDTH = 1000
MIN_HEIGHT = 1000
BLUR_THRESHOLD = 100

def validate_image(content: bytes):

    image = Image.open(io.BytesIO(content))

    if image.format not in ["JPEG", "PNG", "WEBP"]:
        raise ValueError("Unsupported image format")

    if image.width < MIN_WIDTH or image.height < MIN_HEIGHT:
        raise ValueError("Image resolution too low")

    open_cv_image = np.array(image)
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
    variance = cv2.Laplacian(gray, cv2.CV_64F).var()

    if variance < BLUR_THRESHOLD:
        raise ValueError("Image too blurry")