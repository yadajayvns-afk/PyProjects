"""Shared pytest fixtures for the bill organizer test suite."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bill_organizer.config import CategoriesConfig, CategoryRule, FieldsConfig, FieldSpec
from bill_organizer.models import ExtractedBill


@pytest.fixture
def fields_cfg() -> FieldsConfig:
    """A minimal fields config matching the four standard bill fields."""
    return FieldsConfig(
        fields=[
            FieldSpec(name="bill_number", label="Bill No", type="string", required=True),
            FieldSpec(name="bill_date", label="Date", type="date", required=True),
            FieldSpec(name="amount", label="Amount", type="decimal", required=True),
            FieldSpec(name="vendor", label="Vendor", type="string", required=True),
        ]
    )


@pytest.fixture
def categories_cfg() -> CategoriesConfig:
    """A small category ruleset; 'shell' appears in both Fuel and a custom rule."""
    return CategoriesConfig(
        default_category="Uncategorized",
        categories=[
            CategoryRule(name="Food", keywords=["swiggy", "restaurant"]),
            CategoryRule(name="Fuel", keywords=["shell", "fuel"]),
        ],
    )


@pytest.fixture
def sample_bill() -> ExtractedBill:
    """A fully-populated, categorized extracted bill."""
    return ExtractedBill(
        bill_number="INV-001",
        bill_date=date(2026, 5, 12),
        amount=Decimal("123.45"),
        vendor="Swiggy",
        category="Food",
    )


def _write_text_pdf(path: Path, text: str) -> Path:
    """Create a real text-based PDF at ``path`` containing ``text``."""
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def write_text_pdf():
    """Fixture returning a helper that creates a real text-based PDF."""
    return _write_text_pdf
