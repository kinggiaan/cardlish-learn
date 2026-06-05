import re
import os
from rapidocr_onnxruntime import RapidOCR

class CardOCRExtractor:
    def __init__(self):
        # Lazy initialization or direct instantiation
        self.engine = RapidOCR()

    def extract_card_meta(self, image_path: str) -> tuple[str, str]:
        """Extract card number and label from the card front image via OCR.

        Returns:
            (card_no, label) - strings, empty if not found.
        """
        card_no = ""
        label = ""
        
        if not os.path.exists(image_path):
            return "", ""

        # RapidOCR returns a tuple (result, elapse)
        # where result is a list of [box, text, score]
        result, elapse = self.engine(image_path)
        if not result:
            return "", ""

        for box, text, score in result:
            # We skip low-confidence text if needed, but for ID/Label even low confidence can be checked
            text_str = str(text).strip()
            
            # 1. Search for card number (typically 3 digits, e.g. 233)
            if not card_no:
                num_match = re.search(r"\b(\d{3})\b", text_str)
                if num_match:
                    card_no = num_match.group(1)

            # 2. Search for label (characters ending with hyphen, e.g. W-, wr-)
            if not label:
                label_match = re.search(r"\b([A-Za-z]+-)", text_str)
                if label_match:
                    label = label_match.group(1)

        return card_no, label
