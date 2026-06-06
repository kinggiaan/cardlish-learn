import sys
from rapidocr_onnxruntime import RapidOCR

def test_ocr():
    ocr = RapidOCR()
    print("--- FRONT ---")
    front_res, _ = ocr("unified_db/cards/001_card_front.png")
    if front_res:
        for box, text, score in front_res:
            print(f"[{score:.2f}] {text}")
            
    print("\n--- BACK ---")
    back_res, _ = ocr("unified_db/cards/001_card_back.png")
    if back_res:
        for box, text, score in back_res:
            print(f"[{score:.2f}] {text}")

if __name__ == "__main__":
    test_ocr()
