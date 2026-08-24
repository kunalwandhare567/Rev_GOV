"""
Live integration test for Tesseract OCR Service
Tests real image OCR extraction using Pillow and Tesseract.
"""
import os
import pytest
from PIL import Image, ImageDraw
from app.services.ocr_service import OCRService


def test_tesseract_live_ocr(tmp_path):
    # 1. Create a sample image with clear text
    img_path = str(tmp_path / "test_aadhaar.png")
    img = Image.new('RGB', (600, 200), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "Name: Kunal Wandhare", fill=(0, 0, 0))
    draw.text((20, 70), "DOB: 15/03/2004", fill=(0, 0, 0))
    draw.text((20, 110), "Aadhaar: 1234 5678 9012", fill=(0, 0, 0))
    img.save(img_path)

    # 2. Run OCR service
    ocr_svc = OCRService()

    # Note: Disable GEMINI_API_KEY temporarily if set, to test Tesseract fallback directly
    from app.core.config import settings
    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = ""

    try:
        result = ocr_svc.run_ocr(img_path, language="eng")
        
        print("\n--- OCR Test Result ---")
        print(f"Provider: {result.provider}")
        print(f"Raw Text:\n{result.raw_text}")
        print(f"Extracted Fields: {result.extracted_fields}")
        print(f"Confidence: {result.confidence}")

        assert result.provider == "tesseract", f"Expected provider 'tesseract', got '{result.provider}'"
        assert "Kunal" in result.raw_text or "Wandhare" in result.raw_text, f"Text 'Kunal Wandhare' missing from OCR raw_text: {result.raw_text}"
        assert len(result.raw_text) > 0, "OCR extracted raw_text should not be empty"

    finally:
        settings.GEMINI_API_KEY = original_key


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        test_tesseract_live_ocr(Path(tmpdir))
        print("\n✅ Tesseract OCR test PASSED successfully!")
