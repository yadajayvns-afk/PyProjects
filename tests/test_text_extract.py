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
