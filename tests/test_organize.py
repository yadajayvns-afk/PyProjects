"""Tests for file moving and CSV recording."""

from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal

from bill_organizer.models import ExtractedBill
from bill_organizer.organize import (
    append_csv,
    csv_path_for,
    month_label,
    move_bill,
    quarantine_bill,
    target_dir,
)


def test_month_label():
    assert month_label(date(2026, 5, 1)) == "May2026"
    assert month_label(date(2026, 12, 31)) == "December2026"


def test_target_dir_uses_month_and_category(sample_bill, tmp_path):
    d = target_dir(sample_bill, tmp_path)
    assert d == tmp_path / "May2026" / "Food"


def test_move_bill_places_file(sample_bill, tmp_path):
    src = tmp_path / "drop" / "bill.pdf"
    src.parent.mkdir()
    src.write_text("x")
    dest = move_bill(src, sample_bill, tmp_path / "out")
    assert dest.exists()
    assert dest.parent == tmp_path / "out" / "May2026" / "Food"
    assert not src.exists()


def test_move_bill_handles_name_collision(sample_bill, tmp_path):
    out = tmp_path / "out"
    for _ in range(2):
        src = tmp_path / "bill.pdf"
        src.write_text("x")
        move_bill(src, sample_bill, out)
    files = sorted(p.name for p in (out / "May2026" / "Food").iterdir())
    assert files == ["bill (1).pdf", "bill.pdf"]


def test_append_csv_writes_header_once(sample_bill, tmp_path):
    append_csv(sample_bill, tmp_path, "bill.pdf")
    append_csv(sample_bill, tmp_path, "bill2.pdf")
    csv_file = csv_path_for(sample_bill, tmp_path)
    rows = list(csv.reader(csv_file.open(encoding="utf-8")))
    assert rows[0][0] == "bill_no"          # one header
    assert len(rows) == 3                    # header + 2 data rows
    assert rows[1][3] == "Swiggy"
    assert rows[1][2] == "123.45"


def test_csv_path_naming(sample_bill, tmp_path):
    path = csv_path_for(sample_bill, tmp_path)
    assert path.name == "expenseMay2026.csv"
    assert path.parent.name == "May2026"


def test_bill_without_date_falls_back_to_today(tmp_path):
    bill = ExtractedBill(vendor="X", category="Food", amount=Decimal("5"))
    path = csv_path_for(bill, tmp_path)
    assert path.name == f"expense{month_label(date.today())}.csv"


def test_quarantine_moves_to_archive(tmp_path):
    src = tmp_path / "bad.pdf"
    src.write_text("x")
    dest = quarantine_bill(src, tmp_path / "archive" / "failed")
    assert dest.exists()
    assert dest.parent == tmp_path / "archive" / "failed"
    assert not src.exists()
