"""End-to-end test of BillFlow with the extraction crew stubbed out.

The extraction agent (the only part needing an LLM) is monkeypatched to return
a fixed ExtractedBill, so the full detect -> read -> categorize -> file -> record
pipeline runs offline and deterministically.
"""

from __future__ import annotations

import csv
import time
from datetime import date
from decimal import Decimal

from bill_organizer import flow as flow_module
from bill_organizer.flow import BillFlow
from bill_organizer.models import ExtractedBill


def _stub_extract_fields(crew, raw_text, fields_cfg):
    """Return a Swiggy bill regardless of input -- the LLM stand-in."""
    return ExtractedBill(
        bill_number="INV-777",
        bill_date=date(2026, 5, 9),
        amount=Decimal("250.00"),
        vendor="Swiggy",
    )


def test_flow_files_bill_and_writes_csv(
    tmp_path, monkeypatch, fields_cfg, categories_cfg, write_text_pdf
):
    monkeypatch.setattr(flow_module, "extract_fields", _stub_extract_fields)
    monkeypatch.setattr(flow_module, "build_extraction_crew", lambda cfg: object())

    drop = tmp_path / "drop"
    out = tmp_path / "out"
    archive = tmp_path / "archive" / "failed"
    drop.mkdir()

    # A good text PDF, a corrupt file -- backdate so the stability check passes.
    write_text_pdf(
        drop / "good.pdf",
        "Tax Invoice from Swiggy. Invoice No INV-777. Total payable Rs 250.00.",
    )
    (drop / "broken.pdf").write_bytes(b"not a pdf")
    old = time.time() - 60
    for f in drop.iterdir():
        import os

        os.utime(f, (old, old))

    flow = BillFlow(
        drop_dir=drop,
        output_root=out,
        archive_dir=archive,
        fields_cfg=fields_cfg,
        categories_cfg=categories_cfg,
    )
    flow.kickoff()

    # Good bill filed under May2026/Food.
    filed = out / "May2026" / "Food" / "good.pdf"
    assert filed.exists()

    # CSV created with header + one row.
    csv_file = out / "May2026" / "expenseMay2026.csv"
    rows = list(csv.reader(csv_file.open(encoding="utf-8")))
    assert rows[0][0] == "bill_no"
    assert len(rows) == 2
    assert rows[1][3] == "Swiggy"

    # Corrupt file quarantined, not in output.
    assert (archive / "broken.pdf").exists()

    assert flow.state.processed == 1
    assert flow.state.failed == 1


def test_flow_skips_duplicate_on_second_run(
    tmp_path, monkeypatch, fields_cfg, categories_cfg, write_text_pdf
):
    monkeypatch.setattr(flow_module, "extract_fields", _stub_extract_fields)
    monkeypatch.setattr(flow_module, "build_extraction_crew", lambda cfg: object())

    drop = tmp_path / "drop"
    out = tmp_path / "out"
    drop.mkdir()

    def run():
        return BillFlow(
            drop_dir=drop,
            output_root=out,
            archive_dir=tmp_path / "archive",
            fields_cfg=fields_cfg,
            categories_cfg=categories_cfg,
        )

    # First run: file the bill.
    import os

    pdf = write_text_pdf(
        drop / "bill.pdf",
        "Tax Invoice from Swiggy. Invoice No INV-777. Total payable Rs 250.00.",
    )
    old = time.time() - 60
    os.utime(pdf, (old, old))
    run().kickoff()

    # Second run: re-drop the identical file under a new name. The bill was
    # moved out of drop/ on run 1, so copy it back from output/ -- identical
    # content means an identical hash, which the dedup index must catch.
    dup = drop / "dup.pdf"
    dup.write_bytes((out / "May2026" / "Food" / "bill.pdf").read_bytes())
    os.utime(dup, (old, old))
    run().kickoff()

    csv_file = out / "May2026" / "expenseMay2026.csv"
    rows = list(csv.reader(csv_file.open(encoding="utf-8")))
    # Still header + exactly one data row -- the duplicate added nothing.
    assert len(rows) == 2
