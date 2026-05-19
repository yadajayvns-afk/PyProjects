"""Steps 4 & 5 -- move a bill into its month/category folder and record it.

Folder layout produced::

    output/
      May2026/
        Food/
          <bill files>
        Fuel/
        expenseMay2026.csv
"""

from __future__ import annotations

import csv
import shutil
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from .models import ExtractedBill

CSV_HEADER = [
    "bill_no",
    "bill_date",
    "amount",
    "vendor",
    "category",
    "source_file",
    "extracted_at",
]


def month_label(d: date) -> str:
    """Folder/file label for a date, e.g. ``May2026``."""
    return d.strftime("%B%Y")


def month_dir(bill: ExtractedBill, output_root: Path) -> Path:
    """The ``output/<Month><Year>`` directory for a bill.

    Falls back to today's month when the bill has no usable date.
    """
    d = bill.bill_date or date.today()
    return output_root / month_label(d)


def target_dir(bill: ExtractedBill, output_root: Path) -> Path:
    """The ``output/<Month><Year>/<Category>`` directory for a bill."""
    return month_dir(bill, output_root) / bill.category


def _unique_destination(dest_dir: Path, filename: str) -> Path:
    """A non-colliding path inside ``dest_dir`` for ``filename``.

    Appends `` (1)``, `` (2)``... to the stem on collision.
    """
    candidate = dest_dir / filename
    if not candidate.exists():
        return candidate
    stem, suffix = candidate.stem, candidate.suffix
    n = 1
    while True:
        candidate = dest_dir / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def move_bill(src: Path, bill: ExtractedBill, output_root: Path) -> Path:
    """Move a processed bill into its month/category folder; return its new path."""
    dest_dir = target_dir(bill, output_root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(dest_dir, src.name)
    shutil.move(str(src), str(destination))
    return destination


def quarantine_bill(src: Path, archive_dir: Path) -> Path:
    """Move an unreadable/failed bill into the failed-archive folder."""
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(archive_dir, src.name)
    shutil.move(str(src), str(destination))
    return destination


def csv_path_for(bill: ExtractedBill, output_root: Path) -> Path:
    """Path of the per-month CSV, e.g. ``output/May2026/expenseMay2026.csv``."""
    d = bill.bill_date or date.today()
    return month_dir(bill, output_root) / f"expense{month_label(d)}.csv"


def append_csv(bill: ExtractedBill, output_root: Path, source_file: str) -> Path:
    """Append a row for ``bill`` to its month CSV, creating it (with header) if new."""
    csv_file = csv_path_for(bill, output_root)
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    is_new = not csv_file.exists()

    row = {
        "bill_no": bill.bill_number or "",
        "bill_date": bill.bill_date.isoformat() if bill.bill_date else "",
        "amount": _format_amount(bill.amount),
        "vendor": bill.vendor or "",
        "category": bill.category,
        "source_file": source_file,
        "extracted_at": datetime.now().isoformat(timespec="seconds"),
    }

    with csv_file.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        if is_new:
            writer.writeheader()
        writer.writerow(row)

    return csv_file


def _format_amount(amount: Decimal | None) -> str:
    if amount is None:
        return ""
    return f"{amount:.2f}"
