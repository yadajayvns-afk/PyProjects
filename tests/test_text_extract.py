"""Tests for source classification and PDF text extraction."""

from __future__ import annotations

from bill_organizer.text_extract import classify_source, extract_pdf_text, get_bill_text


def test_text_pdf_classified_and_extracted(tmp_path, write_text_pdf):
    pdf = write_text_pdf(tmp_path / "bill.pdf", "Invoice INV-99 Total Rs 500 Vendor Swiggy")
    assert classify_source(pdf) == "text_pdf"
    text = extract_pdf_text(pdf)
    assert "INV-99" in text


def test_get_bill_text_returns_text_and_kind(tmp_path, write_text_pdf):
    pdf = write_text_pdf(tmp_path / "bill.pdf", "Some invoice text long enough to count")
    text, kind = get_bill_text(pdf)
    assert kind == "text_pdf"
    assert "invoice" in text.lower()


def test_empty_file_is_unreadable(tmp_path):
    empty = tmp_path / "broken.pdf"
    empty.write_bytes(b"")
    assert classify_source(empty) == "unreadable"


def test_corrupt_pdf_is_unreadable(tmp_path):
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"this is not a pdf at all")
    assert classify_source(corrupt) == "unreadable"


def test_image_classified_as_needs_ocr(tmp_path):
    from PIL import Image

    img_path = tmp_path / "receipt.png"
    Image.new("RGB", (10, 10), "white").save(img_path)
    assert classify_source(img_path) == "needs_ocr"


def test_extract_ocr_text_dispatches_to_tesseract_engine(tmp_path, monkeypatch):
    from PIL import Image

    from bill_organizer import text_extract

    img_path = tmp_path / "receipt.png"
    Image.new("RGB", (10, 10), "white").save(img_path)

    monkeypatch.setenv("OCR_ENGINE", "tesseract")
    called: dict[str, object] = {}

    def fake_tesseract(path):
        called["path"] = path
        return "tess-out"

    def fake_paddle(path):
        called["paddle"] = path
        return "paddle-out"

    monkeypatch.setattr(text_extract, "_ocr_image_tesseract", fake_tesseract)
    monkeypatch.setattr(text_extract, "_ocr_image_paddle", fake_paddle)

    assert text_extract.extract_ocr_text(img_path) == "tess-out"
    assert called == {"path": img_path}


def test_extract_ocr_text_dispatches_to_paddle_engine(tmp_path, monkeypatch):
    from PIL import Image

    from bill_organizer import text_extract

    img_path = tmp_path / "receipt.png"
    Image.new("RGB", (10, 10), "white").save(img_path)

    monkeypatch.setenv("OCR_ENGINE", "paddle")
    monkeypatch.setattr(text_extract, "_ocr_image_paddle", lambda p: "paddle-out")

    assert text_extract.extract_ocr_text(img_path) == "paddle-out"


def test_extract_ocr_text_paddle_missing_falls_back_to_tesseract(tmp_path, monkeypatch):
    from PIL import Image

    from bill_organizer import text_extract

    img_path = tmp_path / "receipt.png"
    Image.new("RGB", (10, 10), "white").save(img_path)

    monkeypatch.setenv("OCR_ENGINE", "paddle")

    def raise_import(_path):
        raise ImportError("paddleocr not installed")

    monkeypatch.setattr(text_extract, "_ocr_image_paddle", raise_import)
    monkeypatch.setattr(text_extract, "_ocr_image_tesseract", lambda p: "tess-fallback")

    assert text_extract.extract_ocr_text(img_path) == "tess-fallback"
