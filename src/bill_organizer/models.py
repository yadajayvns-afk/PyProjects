"""Pydantic data models: the extracted bill, per-file context, and Flow state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceKind = Literal["text_pdf", "needs_ocr", "unreadable", "unknown"]
BillStatus = Literal["pending", "done", "failed", "skipped"]


class ExtractedBill(BaseModel):
    """The fields pulled from one bill.

    The four nullable fields are filled by the extraction agent; the rest are
    set by deterministic code (categorization, validation).
    """

    bill_number: Optional[str] = None
    bill_date: Optional[date] = None
    amount: Optional[Decimal] = None
    vendor: Optional[str] = None
    category: str = "Uncategorized"
    needs_review: bool = False
    review_reasons: list[str] = Field(default_factory=list)

    def flag(self, reason: str) -> None:
        """Mark this bill as needing manual review, recording why."""
        self.needs_review = True
        if reason not in self.review_reasons:
            self.review_reasons.append(reason)


class BillContext(BaseModel):
    """Working state for a single file as it moves through the pipeline."""

    model_config = {"arbitrary_types_allowed": True}

    source_path: Path
    file_hash: str
    source_kind: SourceKind = "unknown"
    raw_text: str = ""
    bill: Optional[ExtractedBill] = None
    final_path: Optional[Path] = None
    status: BillStatus = "pending"
    error: Optional[str] = None


class BillFlowState(BaseModel):
    """Shared state for one BillFlow run."""

    model_config = {"arbitrary_types_allowed": True}

    drop_dir: Path = Path("drop_bills")
    output_root: Path = Path("output")
    archive_dir: Path = Path("archive/failed")
    discovered: list[Path] = Field(default_factory=list)
    contexts: list[BillContext] = Field(default_factory=list)
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    run_started_at: datetime = Field(default_factory=datetime.now)
