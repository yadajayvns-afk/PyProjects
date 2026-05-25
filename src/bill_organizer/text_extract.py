"""Step 2 -- turn a bill file into raw text.

Two paths:
  * text-based PDF  -> direct extraction with PyMuPDF (fast, exact)
  * scanned PDF / image -> OCR with Tesseract via pdf2image / Pillow

``classify_source`` decides which path applies; ``get_bill_text`` runs it.

For image OCR the engine is selectable via the ``OCR_ENGINE`` env var:
``tesseract`` (default, light) or ``paddle`` (heavier, more accurate on
real-world receipts -- requires ``pip install -e ".[paddle]"``).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .models import SourceKind

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}

# A PDF with fewer extractable characters than this is treated as scanned.
MIN_TEXT_CHARS = 30

DEFAULT_OCR_ENGINE = "tesseract"

# Cached PaddleOCR reader -- model load is slow, so build it once per process.
_paddle_reader: Any | None = None


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


def _ocr_image_tesseract(path: Path) -> str:
    """OCR an image with Tesseract, after shadow/contrast preprocessing."""
    import cv2
    import numpy as np  # noqa: F401  (cv2 returns numpy arrays; explicit import documents the contract)
    import pytesseract

    img = cv2.imread(str(path))
    if img is None:
        # Fallback: let PIL/pytesseract try directly so we still return something.
        from PIL import Image

        with Image.open(path) as pil_img:
            return pytesseract.image_to_string(pil_img)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Background division flattens shadow gradients and faint watermarks
    # by dividing the image by a heavily-blurred estimate of the background.
    bg = cv2.medianBlur(gray, 51)
    norm = cv2.divide(gray, bg, scale=255)
    # CLAHE then sharpens local contrast on the normalised image.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    norm = clahe.apply(norm)
    # Otsu picks a global threshold from the now-flat histogram --
    # cleaner than adaptive threshold, which tends to revive watermarks.
    _, processed = cv2.threshold(norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return pytesseract.image_to_string(processed, config="--oem 1 --psm 6")


def _ocr_image_paddle(path: Path) -> str:
    """OCR an image with PaddleOCR 3.x (cached singleton reader)."""
    global _paddle_reader
    from paddleocr import PaddleOCR

    if _paddle_reader is None:
        # mkldnn is disabled because PaddlePaddle 3.x's oneDNN backend hits an
        # unimplemented attribute error on Windows. Doc orientation / unwarping
        # are off because the bills are already upright photos -- those models
        # add load time and occasional false rotations.
        _paddle_reader = PaddleOCR(
            lang="en",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )

    result = _paddle_reader.predict(str(path))
    lines: list[str] = []
    for page in result or []:
        texts = page.get("rec_texts") if hasattr(page, "get") else None
        if not texts:
            continue
        lines.extend(t for t in texts if t)
    return "\n".join(lines)


def extract_ocr_text(path: Path) -> str:
    """OCR a file to text -- works for image files and scanned PDFs."""
    suffix = path.suffix.lower()

    if suffix in IMAGE_SUFFIXES:
        engine = os.getenv("OCR_ENGINE", DEFAULT_OCR_ENGINE).strip().lower()
        if engine == "paddle":
            try:
                return _ocr_image_paddle(path)
            except ImportError as exc:
                logger.warning(
                    "OCR_ENGINE=paddle but paddleocr is not installed (%s); "
                    "falling back to tesseract. Install with: pip install -e \".[paddle]\"",
                    exc,
                )
        return _ocr_image_tesseract(path)

    if suffix == ".pdf":
        import pytesseract
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
