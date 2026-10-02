"""
One-off, free check: confirms all 8 quotation fixtures extract
cleanly with Docling BEFORE running the real, paid
eval/quotation_extraction_eval.py. No Claude calls, no cost.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quotation_intake.docling_extractor import extract_raw_text

fixtures_dir = Path("eval/quotation_fixtures")
for f in sorted(fixtures_dir.glob("*")):
    print(f"\n{'=' * 60}\n{f.name}\n{'=' * 60}")
    try:
        print(extract_raw_text(str(f)))
    except Exception as e:
        print(f"EXTRACTION FAILED: {e}")
