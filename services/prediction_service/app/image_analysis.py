"""Local, explainable image triage for claim documents.

This is a screening algorithm. It does not turn visible pixels into a payment
amount and must be validated against labelled claim images before automation.
"""
from pathlib import Path


def analyze(path: Path) -> dict:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {'status': 'dependency_missing', 'missing_information': ['برای پردازش محلی تصویر، opencv-python در محیط سرویس نصب نیست'], 'analysis_version': 'local-triage-001'}
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return {'status': 'invalid_image', 'missing_information': ['تصویر قابل خواندن نیست']}
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    # Conservative visual screening: saturated dark/amber regions often need
    # review for soot or burn marks, but are explicitly labelled as candidates.
    dark = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 75]))
    amber = cv2.inRange(hsv, np.array([5, 55, 20]), np.array([35, 255, 180]))
    candidate = cv2.morphologyEx(cv2.bitwise_or(dark, amber), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    ratio = float((candidate > 0).mean() * 100)
    quality = []
    if min(w, h) < 640: quality.append('رزولوشن پایین است')
    if sharpness < 80: quality.append('تصویر تار یا کم‌جزئیات است')
    if brightness < 35 or brightness > 235: quality.append('نور تصویر مناسب نیست')
    return {'status': 'review' if quality or ratio > 1 else 'no_obvious_damage',
            'image': {'width': w, 'height': h, 'sharpness': round(sharpness, 2), 'brightness': round(brightness, 2)},
            'observed_damage_candidates': ['ناحیه تیره/دوده یا تغییر رنگ'] if ratio > 1 else [],
            'visible_damage_ratio_percent': round(ratio, 2),
            'evidence': 'candidate_regions_from_color_and_contrast',
            'missing_information': quality,
            'limitations': ['این نسبت فقط ناحیه قابل مشاهده تصویر است و درصد خسارت مالی نیست.', 'آسیب داخلی و علت حادثه از این الگوریتم اثبات نمی‌شود.']}
