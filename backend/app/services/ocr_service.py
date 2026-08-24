"""
OCR Service — Local document text extraction (free, offline)
Primary: pytesseract + Tesseract OCR
Field extraction: Gemini LLM (structured field parsing from raw OCR text)
"""
import os
import logging
import json
import re
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    raw_text: str
    extracted_fields: dict
    doc_type_detected: str
    confidence: float
    provider: str
    confidence_breakdown: dict = None   # {field_name: confidence_0_to_1}

    def __post_init__(self):
        if self.confidence_breakdown is None:
            # Default: all fields get the overall confidence score
            self.confidence_breakdown = {
                k: self.confidence for k in self.extracted_fields
            }


# Document type detection keywords
DOC_TYPE_KEYWORDS = {
    "AADHAAR_CARD": ["aadhaar", "aadhar", "unique identification", "uidai", "आधार", "आधार कार्ड"],
    "PAN_CARD": ["income tax", "permanent account number", "pan", "पैन"],
    "VOTER_ID": ["election commission", "voter", "electors", "मतदाता"],
    "DRIVING_LICENSE": ["driving licence", "motor vehicles", "dl", "ड्राइविंग"],
    "PASSPORT": ["passport", "republic of india", "पासपोर्ट"],
    "INCOME_PROOF": ["income certificate", "annual income", "उत्पन्न", "वार्षिक"],
    "CASTE_CERTIFICATE": ["caste", "sc", "st", "obc", "जाति"],
    "SELF_DECLARATION": ["declaration", "hereby declare", "घोषणा"],
    "BANK_PASSBOOK": ["bank", "account number", "ifsc", "बैंक"],
    "PAYMENT_RECEIPT": ["receipt", "transaction", "amount paid", "payment", "पावती"],
    "SALARY_SLIP": ["salary", "pay slip", "gross", "net pay", "वेतन"],
    "ELECTRICITY_BILL": ["electricity", "power", "units consumed", "विद्युत"],
}

# Field extraction templates per document type
FIELD_TEMPLATES = {
    "AADHAAR_CARD": ["full_name", "dob", "gender", "address", "aadhaar_number"],
    "PAN_CARD": ["full_name", "dob", "pan_number", "father_name"],
    "VOTER_ID": ["full_name", "dob", "gender", "address", "voter_id"],
    "INCOME_PROOF": ["full_name", "annual_income", "issue_date", "issuing_authority"],
    "PAYMENT_RECEIPT": ["transaction_id", "amount", "date", "reference_number", "payment_method"],
    "CASTE_CERTIFICATE": ["full_name", "caste", "category", "issue_date"],
    "DRIVING_LICENSE": ["full_name", "dob", "dl_number", "address", "validity"],
    "PASSPORT": ["full_name", "dob", "gender", "passport_number", "validity"],
}


class OCRService:
    """
    Extracts text and structured fields from document images/PDFs.
    Primary OCR: Tesseract OCR (C:\\Program Files\\Tesseract-OCR\\tesseract.exe) + pytesseract
    Secondary Vision: Gemini Vision API (if configured)
    """

    def __init__(self):
        from app.core.config import settings
        self.tesseract_path = getattr(settings, "TESSERACT_PATH", None) or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        self.is_tesseract_available = False
        self._init_tesseract()

    def _init_tesseract(self):
        """Initialize and verify Tesseract OCR at runtime startup."""
        if os.name == "nt" and os.path.exists(self.tesseract_path):
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
                self.is_tesseract_available = True
                logger.info(f"[OCR_INIT] ✅ Tesseract OCR loaded and bound to '{self.tesseract_path}'")
            except Exception as e:
                logger.warning(f"[OCR_INIT] ⚠️ PyTesseract binding warning: {e}")
        elif os.name == "nt":
            logger.warning(f"[OCR_INIT] ⚠️ Tesseract binary not found at '{self.tesseract_path}'")

    def run_ocr(self, file_path: str, doc_type: str = None,
                language: str = "eng+hin+mar") -> OCRResult:
        """
        Full OCR processing pipeline:
        1. Log structured OCR start context
        2. Extract raw text & structured fields via Tesseract / Vision
        3. Parse & return OCRResult with per-field confidence breakdown
        """
        from app.core.config import settings

        logger.info(f"[OCR_START] Processing document: file={file_path}, requested_doc_type={doc_type}, language={language}")

        # 1. Try Gemini Vision OCR (if API key available)
        if settings.GEMINI_API_KEY and "replace_with_real_key" not in settings.GEMINI_API_KEY:
            try:
                gemini_result = self._extract_with_gemini_vision(file_path, doc_type)
                if gemini_result and gemini_result.get("extracted_fields"):
                    detected_type = doc_type or gemini_result.get("doc_type_detected", "UNKNOWN")
                    fields = gemini_result["extracted_fields"]
                    breakdown = {k: 0.92 for k in fields}
                    res = OCRResult(
                        raw_text=gemini_result.get("raw_text", ""),
                        extracted_fields=fields,
                        doc_type_detected=detected_type,
                        confidence=0.92,
                        provider="gemini_vision",
                        confidence_breakdown=breakdown,
                    )
                    logger.info(f"[OCR_COMPLETED] Provider=gemini_vision, DocType={res.doc_type_detected}, Fields={list(fields.keys())}")
                    return res
            except Exception as e:
                logger.warning(f"[OCR_GEMINI_FALLBACK] Gemini Vision OCR failed, using Tesseract OCR: {e}")

        # 2. Extract raw text via Tesseract OCR / PyMuPDF
        raw_text = self._extract_text(file_path, language)
        detected_type = doc_type or self.detect_document_type(raw_text)

        if raw_text and raw_text.strip():
            extracted_fields = self._extract_fields(raw_text, detected_type)
            provider = "tesseract"
            base_confidence = 0.85 if self.is_tesseract_available else 0.70
        else:
            extracted_fields = {}
            provider = "mock"
            base_confidence = 0.0
            logger.warning(f"[OCR_EMPTY] No text could be extracted from '{file_path}'. Check image clarity or Tesseract installation.")

        breakdown = {k: base_confidence for k in extracted_fields}

        res = OCRResult(
            raw_text=raw_text or "",
            extracted_fields=extracted_fields,
            doc_type_detected=detected_type,
            confidence=base_confidence,
            provider=provider,
            confidence_breakdown=breakdown,
        )
        logger.info(
            f"[OCR_COMPLETED] Provider={res.provider}, DocType={res.doc_type_detected}, "
            f"Confidence={res.confidence:.2f}, FieldsCount={len(extracted_fields)}, Fields={list(extracted_fields.keys())}"
        )
        return res

    def detect_document_type(self, text: str) -> str:
        """Identify document type from OCR text using keyword matching."""
        text_lower = text.lower()
        scores = {}
        for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[doc_type] = score
        if scores:
            return max(scores, key=scores.get)
        return "UNKNOWN"

    def _extract_with_gemini_vision(self, file_path: str, doc_type: str = None) -> dict:
        """
        Use Gemini 1.5 Flash Vision API to directly extract structured fields
        from any document image or PDF — best for Indian multilingual documents.
        Returns dict with: extracted_fields, raw_text, doc_type_detected, confidence.
        """
        from app.core.config import settings
        import google.generativeai as genai
        import pathlib

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        ext = file_path.lower().rsplit(".", 1)[-1]
        raw_text = ""

        # For PDFs: extract text first, then use Gemini to parse
        if ext == "pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                raw_text = "\n".join(page.get_text() or "" for page in doc).strip()
            except Exception:
                pass
            if not raw_text:
                try:
                    import pypdf
                    reader = pypdf.PdfReader(file_path)
                    raw_text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
                except Exception:
                    pass
            if not raw_text:
                logger.warning("Gemini: PDF has no extractable text (scanned). Cannot use Vision on PDF pages without pdf2image.")
                return {}

            prompt = f"""You are an expert Indian government document parser.
Extract the following fields from this document text and return ONLY a valid JSON object.

Fields to extract:
- applicant_name: Full name of the applicant (string)
- applicant_dob: Date of birth in DD-MM-YYYY format (string)
- aadhaar_number: 12-digit Aadhaar number without spaces (string)
- annual_income: Annual income as a number only without currency symbols (number or string)
- address: Full residential address (string)
- caste_category: Caste category if present e.g. OBC, SC, ST (string or null)
- doc_type: Type of document e.g. AADHAAR_CARD, INCOME_PROOF, PAN_CARD (string)

Rules:
- Return ONLY valid JSON, no explanation text.
- Use null for any field not found.
- Remove spaces from Aadhaar number (e.g. "1234 5678 9012" → "123456789012").
- Normalize date to DD-MM-YYYY format.

Document text:
{raw_text[:4000]}
"""
            response = model.generate_content(prompt)

        else:
            # Image file: send directly as vision input
            image_data = pathlib.Path(file_path).read_bytes()
            import base64
            encoded = base64.b64encode(image_data).decode("utf-8")
            mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

            prompt = f"""You are an expert Indian government document parser.
Look at this document image and extract the following fields, returning ONLY a valid JSON object.

Fields to extract:
- applicant_name: Full name of the applicant
- applicant_dob: Date of birth in DD-MM-YYYY format
- aadhaar_number: 12-digit Aadhaar number without spaces
- annual_income: Annual income as number only
- address: Full residential address
- caste_category: Caste category if present (OBC/SC/ST or null)
- doc_type: Document type (AADHAAR_CARD/INCOME_PROOF/PAN_CARD/etc.)

Rules:
- Return ONLY valid JSON, no explanation text.
- Use null for any field not found in the image.
- Remove spaces from Aadhaar number.
- Normalize date to DD-MM-YYYY.
"""
            response = model.generate_content([
                {"mime_type": mime, "data": encoded},
                prompt
            ])

        # Parse JSON response
        text_resp = response.text.strip()
        json_match = re.search(r'\{.*\}', text_resp, re.DOTALL)
        if not json_match:
            logger.warning(f"Gemini returned non-JSON: {text_resp[:200]}")
            return {}

        parsed = json.loads(json_match.group())

        # Normalize field names to internal slot format
        fields = {}
        for k, v in parsed.items():
            if v is None or v == "null":
                continue
            if k == "applicant_name":   fields["applicant_name"] = str(v).strip()
            elif k == "applicant_dob":  fields["applicant_dob"] = str(v).strip()
            elif k == "aadhaar_number": fields["aadhaar_number"] = re.sub(r'\s+', '', str(v))
            elif k == "annual_income":  fields["annual_income"] = str(v).replace(",", "").strip()
            elif k == "address":        fields["address"] = str(v).strip()
            elif k == "caste_category": fields["caste_category"] = str(v).strip()

        doc_type_detected = parsed.get("doc_type", "UNKNOWN")

        return {
            "extracted_fields": fields,
            "raw_text": raw_text or f"[Image document: {file_path}]",
            "doc_type_detected": doc_type_detected,
            "confidence": 0.92,
        }

    def _extract_text(self, file_path: str, language: str = "eng") -> str:
        """Extract raw text from image or PDF using Tesseract or PyMuPDF/pypdf."""
        if not os.path.exists(file_path):
            logger.error(f"OCR: File not found: {file_path}")
            return ""

        ext = file_path.lower().rsplit(".", 1)[-1]

        # 1. Handle PDF files first (using fitz / pypdf)
        if ext == "pdf":
            pdf_text = self._extract_from_pdf(file_path, language)
            if pdf_text and len(pdf_text.strip()) > 10:
                return pdf_text.strip()

        # 2. Try pytesseract for images or scanned PDFs
        try:
            import pytesseract
            from PIL import Image

            # Auto-detect Tesseract path from env/settings or Windows default
            env_tesseract_path = getattr(settings, "TESSERACT_PATH", None) or os.getenv("TESSERACT_PATH")
            tesseract_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            
            if env_tesseract_path and os.path.exists(env_tesseract_path):
                pytesseract.pytesseract.tesseract_cmd = env_tesseract_path
            elif os.name == "nt" and os.path.exists(tesseract_win_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_win_path

            img = Image.open(file_path)
            text = pytesseract.image_to_string(img, lang=language)
            if text and text.strip():
                return text.strip()
        except Exception as e:
            logger.warning(f"pytesseract extraction unavailable/failed: {e}")

        # 3. Fallback mock extract
        return self._mock_extract(file_path)

    def _extract_from_pdf(self, file_path: str, language: str) -> str:
        """Extract text from PDF — tries fitz (PyMuPDF) → pypdf → pdf2image/pytesseract."""
        # Try PyMuPDF (fitz)
        try:
            import fitz
            doc = fitz.open(file_path)
            text = "\n".join(page.get_text() or "" for page in doc).strip()
            if text:
                return text
        except Exception:
            pass

        # Try pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
            if text:
                return text
        except Exception:
            pass

        # Try pdf2image + pytesseract if installed
        try:
            from pdf2image import convert_from_path
            import pytesseract
            tesseract_win_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.name == "nt" and os.path.exists(tesseract_win_path):
                pytesseract.pytesseract.tesseract_cmd = tesseract_win_path
            pages = convert_from_path(file_path, dpi=300)
            texts = []
            for page in pages:
                texts.append(pytesseract.image_to_string(page, lang=language))
            return "\n".join(texts).strip()
        except Exception as e:
            logger.warning(f"PDF OCR failed: {e}")
            return ""


    def _extract_fields(self, raw_text: str, doc_type: str) -> dict:
        """
        Use LLM to extract structured fields from raw OCR text.
        Falls back to regex patterns if LLM unavailable.
        """
        if not raw_text.strip():
            return {}

        target_fields = FIELD_TEMPLATES.get(doc_type, ["full_name", "dob", "address"])

        try:
            from app.orchestration.nlu.local_llm import LocalLLM
            llm = LocalLLM()
            prompt = f"""Extract the following fields from this document text.
Return a JSON object with exactly these keys: {target_fields}
If a field is not found, use null.
Normalize dates to YYYY-MM-DD format.
Normalize names to Title Case.

Document text:
{raw_text[:3000]}

Return ONLY valid JSON, no other text."""

            response = llm.generate_raw(prompt)

            # Parse JSON from response
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            logger.warning(f"LLM field extraction failed: {e}, falling back to regex")

        # Regex fallback for common fields
        return self._regex_extract(raw_text, doc_type)

    def _regex_extract(self, text: str, doc_type: str) -> dict:
        """Basic regex-based field extraction fallback."""
        fields = {}

        # DOB patterns
        dob_match = re.search(
            r'(?:dob|date of birth|जन्म(?:\s*तारीख)?)[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            text, re.IGNORECASE
        )
        if dob_match:
            fields["dob"] = self._normalize_date(dob_match.group(1))

        # Name patterns
        name_match = re.search(r'(?:name|नाम)[:\s]+([A-Za-z\s]+)', text, re.IGNORECASE)
        if name_match:
            fields["full_name"] = name_match.group(1).strip().title()

        # Aadhaar number (12 digits)
        aadh_match = re.search(r'\b(\d{4}\s\d{4}\s\d{4}|\d{12})\b', text)
        if aadh_match and doc_type == "AADHAAR_CARD":
            fields["aadhaar_number"] = aadh_match.group(1).replace(" ", "")[-4:]  # Only last 4

        # Amount (for receipts)
        amt_match = re.search(r'(?:amount|₹|rs\.?)[:\s]*(\d+(?:\.\d{2})?)', text, re.IGNORECASE)
        if amt_match:
            fields["amount"] = float(amt_match.group(1))

        # Transaction ID
        txn_match = re.search(r'(?:txn|transaction\s*id|ref)[:\s#]+([A-Z0-9]+)', text, re.IGNORECASE)
        if txn_match:
            fields["transaction_id"] = txn_match.group(1)

        return fields

    def _normalize_date(self, date_str: str) -> str:
        """Normalize various date formats to YYYY-MM-DD."""
        import re
        parts = re.split(r'[-/]', date_str)
        if len(parts) == 3:
            d, m, y = parts
            if len(y) == 2:
                y = "20" + y if int(y) < 50 else "19" + y
            if len(d) == 4:  # Already year-first
                return f"{d}-{m.zfill(2)}-{y.zfill(2)}"
            return f"{y}-{m.zfill(2)}-{d.zfill(2)}"
        return date_str

    def _mock_extract(self, file_path: str) -> str:
        """Mock OCR for demo when Tesseract not installed."""
        filename = os.path.basename(file_path).lower()
        if "aadhaar" in filename or "aadhar" in filename:
            return "Kunal Wadhare\nDate of Birth: 15/03/2004\nGender: Male\nNagpur, Maharashtra\nAadhaar: 1234 5678 9012"
        elif "income" in filename:
            return "Income Certificate\nName: Kunal Wandhare\nAnnual Income: Rs. 1,50,000\nIssued: Revenue Department Nagpur"
        return f"Document: {filename}\n[OCR mock — install tesseract for real extraction]"
