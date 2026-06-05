from pathlib import Path
from typing import List
from PIL import Image, ImageDraw
from core.pairing import CardPair

def make_review_contact_sheet(pairs: List[CardPair], out_dir: Path, pdf_name: str, thumb_w: int = 220) -> Path:
    """Generate a visual review sheet for the current scan run, named review_contact_sheet_[pdf_name].png."""
    rows = []
    for p in pairs:
        front_path = out_dir / p.front_image
        back_path = out_dir / p.back_image
        
        front = Image.open(front_path).convert("RGB")
        back = Image.open(back_path).convert("RGB")
        
        def thumb(img: Image.Image) -> Image.Image:
            ratio = thumb_w / img.width
            return img.resize((thumb_w, int(img.height * ratio)), Image.LANCZOS)
            
        rows.append((p, thumb(front), thumb(back)))
        
    row_h = max(max(f.height, b.height) for _, f, b in rows) + 52 if rows else 100
    sheet_w = thumb_w * 2 + 430
    sheet_h = row_h * len(rows) + 30
    sheet = Image.new("RGB", (sheet_w, sheet_h), "white")
    draw = ImageDraw.Draw(sheet)
    
    y = 15
    for p, f, b in rows:
        draw.text((15, y), f"{p.cell}  {p.card_no} {p.label}".strip(), fill="black")
        draw.text((15, y + 18), f"QR: {p.qr_url or '-'}", fill="black")
        draw.text((15, y + 36), f"front p{p.front_page} / back p{p.back_page}" + ("  REVIEW" if p.needs_review else ""), fill="black")
        sheet.paste(f, (420, y))
        sheet.paste(b, (420 + thumb_w + 15, y))
        y += row_h
        
    out_path = out_dir / f"review_contact_sheet_{pdf_name}.png"
    sheet.save(out_path)
    return out_path
