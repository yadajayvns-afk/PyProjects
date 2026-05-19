"""Tests for the deterministic keyword categorizer."""

from __future__ import annotations

from bill_organizer.categorize import categorize_with_text
from bill_organizer.models import ExtractedBill


def test_match_by_vendor(categories_cfg):
    bill = ExtractedBill(vendor="Swiggy Foods Pvt Ltd")
    category, ambiguous = categorize_with_text(bill, "", categories_cfg)
    assert category == "Food"
    assert ambiguous is False


def test_match_by_raw_text(categories_cfg):
    bill = ExtractedBill(vendor="Unknown Merchant")
    category, ambiguous = categorize_with_text(bill, "Shell petrol station", categories_cfg)
    assert category == "Fuel"
    assert ambiguous is False


def test_no_match_returns_default(categories_cfg):
    bill = ExtractedBill(vendor="Some Bookstore")
    category, ambiguous = categorize_with_text(bill, "books and stationery", categories_cfg)
    assert category == "Uncategorized"
    assert ambiguous is False


def test_multiple_matches_flagged_ambiguous(categories_cfg):
    # Text contains both a Food keyword and a Fuel keyword.
    bill = ExtractedBill(vendor="Restaurant near the Shell pump")
    category, ambiguous = categorize_with_text(bill, "", categories_cfg)
    assert category == "Food"  # first by config order
    assert ambiguous is True


def test_case_insensitive_by_default(categories_cfg):
    bill = ExtractedBill(vendor="SWIGGY")
    category, _ = categorize_with_text(bill, "", categories_cfg)
    assert category == "Food"
