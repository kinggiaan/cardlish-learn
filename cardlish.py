#!/usr/bin/env python3
"""Cardlish Card Manager — Unified launcher for card import workflows.

Quick entry point for both photo import and PDF scan pipelines.

Usage:
  python cardlish.py              # Interactive menu
  python cardlish.py photo        # Jump to photo import
  python cardlish.py scan         # Jump to PDF scan
"""

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".heic"}
FRONT_SUFFIXES = ("_front", "_f", "_truoc")
BACK_SUFFIXES = ("_back", "_b", "_sau")


def find_photo_pairs(search_dir: Path) -> list[tuple[Path, Path]]:
    """Find front/back image pairs in a directory."""
    images = [f for f in search_dir.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS]

    front_map = {}
    back_map = {}
    for img in images:
        stem_lower = img.stem.lower()
        for suffix in FRONT_SUFFIXES:
            if stem_lower.endswith(suffix):
                base = img.stem[:len(img.stem) - len(suffix)].lower()
                front_map[base] = img
                break
        for suffix in BACK_SUFFIXES:
            if stem_lower.endswith(suffix):
                base = img.stem[:len(img.stem) - len(suffix)].lower()
                back_map[base] = img
                break

    pairs = []
    for base_key in sorted(front_map.keys()):
        if base_key in back_map:
            pairs.append((front_map[base_key], back_map[base_key]))
    return pairs


def find_pending_pdfs() -> tuple[list[Path], list[Path]]:
    """Find PDFs in 'Card scan/' and check which are already processed."""
    scan_dir = PROJECT_ROOT / "Card scan"
    out_dir = PROJECT_ROOT / "unified_db"

    if not scan_dir.exists():
        return [], []

    all_pdfs = sorted(scan_dir.glob("*.pdf"))
    pending = []
    processed = []
    for pdf in all_pdfs:
        contact_sheet = out_dir / f"review_contact_sheet_{pdf.stem}.png"
        if contact_sheet.exists():
            processed.append(pdf)
        else:
            pending.append(pdf)
    return pending, processed


def show_status():
    """Show current status of both pipelines."""
    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║            🎴 Cardlish Card Manager                     ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # Photo pairs in project root
    photo_pairs = find_photo_pairs(PROJECT_ROOT)
    if photo_pairs:
        print(f"\n  📷 Tìm thấy {len(photo_pairs)} cặp ảnh thẻ ở project root:")
        for front, back in photo_pairs:
            print(f"     • {front.name}  +  {back.name}")
    else:
        print(f"\n  📷 Không có ảnh thẻ nào ở project root")
        print(f"     (Đặt ảnh theo tên: thẻ_XXX_front.jpg + thẻ_XXX_back.jpg)")

    # PDF scans
    pending_pdfs, processed_pdfs = find_pending_pdfs()
    scan_dir = PROJECT_ROOT / "Card scan"
    if scan_dir.exists():
        total = len(pending_pdfs) + len(processed_pdfs)
        print(f"\n  📄 PDF scans trong 'Card scan/': {total} file")
        if pending_pdfs:
            print(f"     🆕 Chưa xử lý: {len(pending_pdfs)}")
            for pdf in pending_pdfs[:5]:
                print(f"        • {pdf.name}")
            if len(pending_pdfs) > 5:
                print(f"        ... và {len(pending_pdfs) - 5} file khác")
        if processed_pdfs:
            print(f"     ✅ Đã xử lý: {len(processed_pdfs)}")
    else:
        print(f"\n  📄 Thư mục 'Card scan/' không tồn tại")

    # Database stats
    import json
    manifest = PROJECT_ROOT / "unified_db" / "data" / "cards_manifest.json"
    if manifest.exists():
        cards = json.loads(manifest.read_text(encoding="utf-8"))
        print(f"\n  🗃️  Database: {len(cards)} thẻ")
    print()


def menu_photo_import():
    """Handle photo import workflow."""
    photo_pairs = find_photo_pairs(PROJECT_ROOT)

    if not photo_pairs:
        print("\n  ❌ Không tìm thấy cặp ảnh nào ở project root!")
        print("  📌 Hướng dẫn: Đặt 2 ảnh với tên như sau:")
        print("     thẻ_024_front.jpg  +  thẻ_024_back.jpg")
        print("     card01_f.jpg       +  card01_b.jpg")
        print("     abc_truoc.png      +  abc_sau.png")
        return

    print(f"\n  📷 Tìm thấy {len(photo_pairs)} cặp ảnh:")
    for i, (front, back) in enumerate(photo_pairs, 1):
        print(f"     {i}. {front.name}  ↔  {back.name}")

    print(f"\n  Chọn:")
    print(f"     [a] Import TẤT CẢ {len(photo_pairs)} cặp")
    if len(photo_pairs) > 1:
        print(f"     [1-{len(photo_pairs)}] Import 1 cặp cụ thể")
    else:
        print(f"     [1] Import cặp này")
    print(f"     [d] Dry-run (xem trước, không ghi file)")
    print(f"     [q] Quay lại")

    choice = input("\n  👉 ").strip().lower()

    if choice == "q":
        return

    dry_run = choice == "d"
    if dry_run:
        pairs_to_import = photo_pairs
    elif choice == "a":
        pairs_to_import = photo_pairs
    elif choice.isdigit() and 1 <= int(choice) <= len(photo_pairs):
        pairs_to_import = [photo_pairs[int(choice) - 1]]
    else:
        print("  ❌ Lựa chọn không hợp lệ")
        return

    # Build command for each pair
    for front, back in pairs_to_import:
        cmd = [
            sys.executable, str(PROJECT_ROOT / "import_card_images.py"),
            "--front", str(front),
            "--back", str(back),
        ]
        if dry_run:
            cmd.append("--dry-run")

        print(f"\n  🚀 Đang xử lý: {front.name} + {back.name}")
        subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if not dry_run and pairs_to_import:
        # Ask if user wants to clean up source photos
        print(f"\n  🧹 Xóa ảnh gốc đã import?")
        print(f"     [y] Có, xóa")
        print(f"     [n] Không, giữ lại")
        cleanup = input("  👉 ").strip().lower()
        if cleanup == "y":
            for front, back in pairs_to_import:
                front.unlink(missing_ok=True)
                back.unlink(missing_ok=True)
                print(f"     🗑️  Đã xóa {front.name}, {back.name}")


def menu_pdf_scan():
    """Handle PDF scan workflow."""
    pending, processed = find_pending_pdfs()

    if not pending:
        print(f"\n  ✅ Tất cả PDF đã được xử lý! ({len(processed)} files)")
        print(f"     Dùng --force để xử lý lại: python batch_split.py --force")
        print(f"\n  Chọn:")
        print(f"     [f] Force re-process tất cả")
        print(f"     [q] Quay lại")
        choice = input("\n  👉 ").strip().lower()
        if choice == "f":
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "batch_split.py"), "--force"],
                cwd=str(PROJECT_ROOT),
            )
        return

    print(f"\n  📄 {len(pending)} PDF chưa xử lý:")
    for i, pdf in enumerate(pending, 1):
        print(f"     {i}. {pdf.name}")

    print(f"\n  Chọn:")
    print(f"     [a] Xử lý TẤT CẢ {len(pending)} PDF mới")
    print(f"     [1-{len(pending)}] Xử lý 1 file cụ thể")
    print(f"     [q] Quay lại")

    choice = input("\n  👉 ").strip().lower()

    if choice == "q":
        return
    elif choice == "a":
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "batch_split.py")],
            cwd=str(PROJECT_ROOT),
        )
    elif choice.isdigit() and 1 <= int(choice) <= len(pending):
        pdf = pending[int(choice) - 1]
        subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "split_cardlish_pdf.py"),
             str(pdf), "--out", "unified_db"],
            cwd=str(PROJECT_ROOT),
        )
    else:
        print("  ❌ Lựa chọn không hợp lệ")


def main():
    # Allow direct subcommand: python cardlish.py photo / scan
    if len(sys.argv) > 1:
        cmd = sys.argv[1].lower()
        if cmd in ("photo", "photos", "img", "image", "ảnh", "anh"):
            show_status()
            menu_photo_import()
            return
        elif cmd in ("scan", "pdf", "batch"):
            show_status()
            menu_pdf_scan()
            return
        elif cmd in ("status", "info"):
            show_status()
            return

    # Interactive menu loop
    while True:
        show_status()

        print("  ┌─────────────────────────────────┐")
        print("  │  [1] 📷  Import từ ảnh (camera)  │")
        print("  │  [2] 📄  Scan từ PDF             │")
        print("  │  [3] 🔨  Build dist              │")
        print("  │  [q] 🚪  Thoát                   │")
        print("  └─────────────────────────────────┘")

        choice = input("\n  👉 ").strip().lower()

        if choice == "1":
            menu_photo_import()
        elif choice == "2":
            menu_pdf_scan()
        elif choice == "3":
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "scripts" / "build_deploy.py"), "-o", "dist"],
                cwd=str(PROJECT_ROOT),
            )
            input("\n  Nhấn Enter để tiếp tục...")
        elif choice in ("q", "exit", "quit"):
            print("\n  👋 Bye!")
            break
        else:
            print("  ❌ Lựa chọn không hợp lệ")


if __name__ == "__main__":
    main()
