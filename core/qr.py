import cv2

def decode_qr(img_bgr) -> str:
    """Detect and decode QR code in a BGR image."""
    detector = cv2.QRCodeDetector()
    for scale in (1.0, 1.5, 2.0, 3.0):
        if scale == 1.0:
            candidate = img_bgr
        else:
            candidate = cv2.resize(img_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        for variant in (candidate, cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY)):
            val, _points, _straight = detector.detectAndDecode(variant)
            if val:
                return val.strip()
    return ""
