#!/usr/bin/env python3
"""
Batch process all Cardlish PDF scans from the "Card scan" folder.

This script:
1. Discovers all scan*.pdf files in the input folder.
2. Detects which PDFs have already been processed (by checking for contact sheets).
3. Processes only the remaining PDFs, in numerical order.

Usage:
  python batch_split.py                         # Process new scans from "Card scan/"
  python batch_split.py --force                 # Reprocess ALL scans
  python batch_split.py --scan-dir "My Scans"   # Custom scan folder
  python batch_split.py --dpi 300               # Higher resolution
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

# Configure stdout to use UTF-8 to prevent console encoding issues on Windows
sys.stdout.reconfigure(encoding='utf-8')

def natural_sort_key(path: Path):
    """Sort scan0001.pdf, scan0002.pdf, ... numerically."""
    import re
    parts = re.findall(r'(\d+)', path.stem)
    return [int(p) for p in parts] if parts else [path.stem]

def main():
    parser = argparse.ArgumentParser(
        description="Batch process all Cardlish PDF scans."
    )
    parser.add_argument(
        "--scan-dir", type=Path, default=Path("Card scan"),
        help="Folder containing scanned PDF files (default: 'Card scan')."
    )
    parser.add_argument(
        "--out", type=Path, default=Path("unified_db"),
        help="Output directory for the card database (default: 'unified_db')."
    )
    parser.add_argument(
        "--dpi", type=int, default=200,
        help="DPI resolution for rendering PDF pages (default: 200)."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Reprocess all PDFs, even those already processed."
    )
    args = parser.parse_args()

    # Resolve paths
    project_root = Path(__file__).resolve().parent
    scan_dir = project_root / args.scan_dir if not args.scan_dir.is_absolute() else args.scan_dir
    out_dir = project_root / args.out if not args.out.is_absolute() else args.out

    if not scan_dir.exists():
        print(f"❌ Error: Scan folder not found: {scan_dir}")
        sys.exit(1)

    # Find all PDF files (scan*.pdf pattern, plus any other .pdf files)
    all_pdfs = sorted(scan_dir.glob("scan*.pdf"), key=natural_sort_key)
    
    # Also include any non-scan PDFs (but exclude test files)
    other_pdfs = sorted(
        [p for p in scan_dir.glob("*.pdf") if not p.stem.startswith("scan") and not p.stem.startswith("test")],
        key=natural_sort_key
    )
    all_pdfs.extend(other_pdfs)

    if not all_pdfs:
        print(f"❌ No PDF files found in: {scan_dir}")
        sys.exit(1)

    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║          🎴 Cardlish Batch Card Splitter                ║")
    print(f"╠══════════════════════════════════════════════════════════╣")
    print(f"║  Scan folder : {str(scan_dir):<41s} ║")
    print(f"║  Output      : {str(out_dir):<41s} ║")
    print(f"║  DPI         : {args.dpi:<41d} ║")
    print(f"║  Total PDFs  : {len(all_pdfs):<41d} ║")
    print(f"╚══════════════════════════════════════════════════════════╝")
    print()

    # Determine which PDFs still need processing
    if args.force:
        pending = all_pdfs
        skipped = []
    else:
        pending = []
        skipped = []
        for pdf in all_pdfs:
            contact_sheet = out_dir / f"review_contact_sheet_{pdf.stem}.png"
            if contact_sheet.exists():
                skipped.append(pdf)
            else:
                pending.append(pdf)

    if skipped:
        print(f"⏭️  Skipping {len(skipped)} already-processed PDFs:")
        for pdf in skipped:
            print(f"   ✅ {pdf.name}")
        print()

    if not pending:
        print("🎉 All PDFs have already been processed! Use --force to reprocess.")
        return

    print(f"📋 Processing {len(pending)} PDF(s):")
    for i, pdf in enumerate(pending, 1):
        print(f"   {i:2d}. {pdf.name}")
    print()

    # Process each PDF
    success_count = 0
    fail_count = 0
    failed_files = []
    total_start = time.time()

    for i, pdf in enumerate(pending, 1):
        print(f"{'='*60}")
        print(f"  [{i}/{len(pending)}] Processing: {pdf.name}")
        print(f"{'='*60}")

        start = time.time()
        try:
            result = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "split_cardlish_pdf.py"),
                    str(pdf),
                    "--out", str(out_dir),
                    "--dpi", str(args.dpi),
                ],
                check=True,
                cwd=str(project_root),
            )
            elapsed = time.time() - start
            success_count += 1
            print(f"  ✅ {pdf.name} completed in {elapsed:.1f}s")
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start
            fail_count += 1
            failed_files.append(pdf.name)
            print(f"  ❌ {pdf.name} FAILED after {elapsed:.1f}s (exit code {e.returncode})")
        except Exception as e:
            fail_count += 1
            failed_files.append(pdf.name)
            print(f"  ❌ {pdf.name} FAILED: {e}")
        
        print()

    total_elapsed = time.time() - total_start

    # Summary
    print(f"╔══════════════════════════════════════════════════════════╗")
    print(f"║                   📊 Batch Summary                      ║")
    print(f"╠══════════════════════════════════════════════════════════╣")
    print(f"║  Total PDFs processed : {success_count + fail_count:<33d} ║")
    print(f"║  ✅ Successful        : {success_count:<33d} ║")
    print(f"║  ❌ Failed            : {fail_count:<33d} ║")
    print(f"║  ⏭️  Skipped (cached)  : {len(skipped):<33d} ║")
    print(f"║  ⏱️  Total time        : {total_elapsed:.1f}s{' ' * max(0, 30 - len(f'{total_elapsed:.1f}s'))} ║")
    print(f"╚══════════════════════════════════════════════════════════╝")

    if failed_files:
        print(f"\n⚠️  Failed files:")
        for f in failed_files:
            print(f"   - {f}")
        print(f"\nRetry with: python batch_split.py --force")

    if success_count > 0:
        print(f"\n🎉 Done! View results:")
        print(f"   - Card database: {out_dir}")
        print(f"   - Contact sheets: {out_dir}/review_contact_sheet_*.png")
        print(f"   - Web viewer: dist/index.html")


if __name__ == "__main__":
    main()
