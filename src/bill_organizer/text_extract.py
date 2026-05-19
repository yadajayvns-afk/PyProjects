"""Step 2 -- turn a bill file into raw text.

Two paths:
  * text-based PDF  -> direct extraction with PyMuPDF (fast, exact)
  * scanned PDF / image -> OCR with Tesseract via pdf2image / Pillow

``classify_source`` decides which path applies; ``get_bill_text`` runs it.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .models import SourceKind

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

# A PDF with fewer extractable characters than this is treated as scanned.
MIN_TEXT_CHARS = 30


def _pdf_text(path: Path) -> str:
    """Extract embedded text from every page of a PDF (empty if none/scanned)."""
    import pymupdf  # imported lazily so the module loads without the dep present

    parts: list[str] = []
    with pymupdf.open(path) as doc:
        if doc.needs_pass:  # encrypted and we have no password
            raise ValueError("PDF is encrypted")
        for page in doc:
            parts.append(page.get_text())
    return "\n".join(parts)


def classify_source(path: Path) -> SourceKind:
    """Decide how a file's text should be extracted.

    Returns ``text_pdf``, ``needs_ocr``, or ``unreadable``.
    """
    suffix = path.suffix.lower()

    try:
        if path.stat().st_size == 0:
            return "unreadable"
    except OSError:
        return "unreadable"

    if suffix in IMAGE_SUFFIXES:
        return "needs_ocr"

    if suffix == ".pdf":
        try:
            text = _pdf_text(path)
        except Exception as exc:  # corrupt / encrypted / unreadable PDF
            logger.warning("Cannot read PDF %s: %s", path.name, exc)
            return "unreadable"
        return "text_pdf" if len(text.strip()) >= MIN_TEXT_CHARS else "needs_ocr"

    return "unreadable"


def extract_pdf_text(path: Path) -> str:
    """Extract embedded text from a text-based PDF."""
    return _pdf_text(path)


def extract_ocr_text(path: Path) -> str:
    """OCR a file to text -- works for image files and scanned PDFs."""
    import pytesseract
    from PIL import Image

    suffix = path.suffix.lower()

    if suffix in IMAGE_SUFFIXES:
        with Image.open(path) as img:
            return pytesseract.image_to_string(img)

    if suffix == ".pdf":
        from pdf2image import convert_from_path

        pages = convert_from_path(path)  # one PIL image per page
        return "\n".join(pytesseract.image_to_string(page) for page in pages)

    raise ValueError(f"Unsupported file type for OCR: {path.suffix}")


def get_bill_text(path: Path) -> tuple[str, SourceKind]:
    """Return ``(raw_text, source_kind)`` for a bill file.

    For an unreadable file the text is empty and kind is ``unreadable``.
    """
    kind = classify_source(path)
    if kind == "text_pdf":
        return extract_pdf_text(path), kind
    if kind == "needs_ocr":
        try:
            return extract_ocr_text(path), kind
        except Exception as exc:
            logger.warning("OCR failed for %s: %s", path.name, exc)
            return "", "unreadable"
    return "", "unreadable"
