"""
Decode QR directly from card images to see exactly what URL they contain.
"""
import cv2
import sys
import os

CARDS_DIR = "unified_db/cards"

# Pick a few sample card front images
samples = [
    "001_card_front.png",
    "005_card_front.png", 
    "227_card_front.png",
    "233_w_front.png",
    "212_b_front.png",
]

detector = cv2.QRCodeDetector()

for fname in samples:
    path = os.path.join(CARDS_DIR, fname)
    if not os.path.exists(path):
        print(f"[SKIP] {fname} not found")
        continue
    
    img = cv2.imread(path)
    if img is None:
        print(f"[ERR] Cannot read {fname}")
        continue
    
    print(f"\n{'='*60}")
    print(f"Card: {fname}")
    print(f"  Image size: {img.shape[1]}x{img.shape[0]}")
    
    # Try multiple scales
    found = False
    for scale in (1.0, 1.5, 2.0, 3.0):
        if scale == 1.0:
            candidate = img
        else:
            candidate = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        
        for label, variant in [("color", candidate), ("gray", cv2.cvtColor(candidate, cv2.COLOR_BGR2GRAY))]:
            val, points, straight = detector.detectAndDecode(variant)
            if val:
                print(f"  QR FOUND (scale={scale}, {label}):")
                print(f"  >>> RAW QR DATA: {repr(val)}")
                print(f"  >>> URL: {val.strip()}")
                
                # Check if it's a direct audio link
                lower = val.lower()
                if any(ext in lower for ext in ['.mp3', '.m4a', '.wav', '.ogg', '.webm']):
                    print(f"  >>> THIS IS A DIRECT AUDIO FILE LINK!")
                elif 'cardlish.com' in lower:
                    print(f"  >>> This is a cardlish.com webpage URL")
                else:
                    print(f"  >>> Unknown URL type")
                
                found = True
                break
        if found:
            break
    
    if not found:
        print(f"  [NO QR FOUND]")

print(f"\n{'='*60}")
print("Done.")
