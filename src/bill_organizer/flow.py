"""The BillFlow -- a CrewAI Flow orchestrating the bill pipeline.

The Flow gives typed shared state and ordered steps. Each step is mostly
deterministic Python; the one fuzzy step (field extraction) delegates to a
single-agent Crew (see ``crews/extraction_crew.py``).

Per-file branching (text-PDF vs OCR vs unreadable) is a plain ``if`` inside the
per-file loop -- CrewAI ``@router`` fires once per run, not once per file, so a
loop is the honest fit here.
"""

from __future__ import annotations

import logging
from pathlib import Path

from crewai.flow.flow import Flow, listen, start

from .categorize import categorize_with_text
from .config import (
    CategoriesConfig,
    FieldsConfig,
    load_categories_config,
    load_fields_config,
)
from .crews.extraction_crew import build_extraction_crew, extract_fields
from .detect import (
    file_hash,
    find_new_bills,
    load_processed_index,
    save_processed_index,
)
from .models import BillContext, BillFlowState, ExtractedBill
from .organize import append_csv, move_bill, quarantine_bill
from .text_extract import get_bill_text

logger = logging.getLogger(__name__)


class BillFlow(Flow[BillFlowState]):
    """Detect, read, categorize, file, and record bills from a drop folder."""

    def __init__(
        self,
        drop_dir: Path = Path("drop_bills"),
        output_root: Path = Path("output"),
        archive_dir: Path = Path("archive/failed"),
        fields_cfg: FieldsConfig | None = None,
        categories_cfg: CategoriesConfig | None = None,
    ) -> None:
        super().__init__()
        self.state.drop_dir = drop_dir
        self.state.output_root = output_root
        self.state.archive_dir = archive_dir
        self._fields_cfg = fields_cfg or load_fields_config()
        self._categories_cfg = categories_cfg or load_categories_config()
        self._index_path = output_root / ".processed_index.json"
        # The extraction crew is built lazily so a discovery-only run (no new
        # bills) never needs an LLM API key.
        self._crew = None

    # -- Step 1 ------------------------------------------------------------
    @start()
    def detect_bills(self) -> None:
        """Find new, non-duplicate bills in the drop folder."""
        self.state.discovered = find_new_bills(self.state.drop_dir, self._index_path)
        logger.info("Discovered %d new bill(s).", len(self.state.discovered))

    # -- Steps 2-5: per-file pipeline -------------------------------------
    @listen(detect_bills)
    def process_bills(self) -> None:
        """Process each discovered bill end to end, one at a time."""
        index = load_processed_index(self._index_path)

        for path in self.state.discovered:
            ctx = BillContext(source_path=path, file_hash=_safe_hash(path))
            self.state.contexts.append(ctx)
            try:
                self._process_one(ctx)
            except Exception as exc:  # never let one bill abort the batch
                logger.exception("Unhandled error processing %s", path.name)
                ctx.status = "failed"
                ctx.error = str(exc)
                self._quarantine(ctx)

            if ctx.status == "done":
                self.state.processed += 1
            elif ctx.status == "skipped":
                self.state.skipped += 1
            else:
                self.state.failed += 1

            # Record the hash so a re-drop of this file is skipped next run.
            if ctx.file_hash:
                index[ctx.file_hash] = path.name

        save_processed_index(self._index_path, index)

    # -- Step 6 ------------------------------------------------------------
    @listen(process_bills)
    def finalize(self) -> str:
        """Print and return a one-line run summary."""
        s = self.state
        summary = (
            f"Bill run complete: {s.processed} filed, "
            f"{s.skipped} skipped, {s.failed} failed."
        )
        logger.info(summary)
        return summary

    # -- internals --------------------------------------------------------
    def _process_one(self, ctx: BillContext) -> None:
        """Run the full text -> extract -> categorize -> file pipeline for one bill."""
        # Step 2: read text (text-PDF path or OCR path, decided inside).
        ctx.raw_text, ctx.source_kind = get_bill_text(ctx.source_path)
        if ctx.source_kind == "unreadable":
            logger.warning("Unreadable bill, quarantining: %s", ctx.source_path.name)
            ctx.status = "failed"
            ctx.error = "could not extract text"
            self._quarantine(ctx)
            return

        # Step 3a: extract fields via the single-agent crew.
        if self._crew is None:
            self._crew = build_extraction_crew(self._fields_cfg)
        bill: ExtractedBill = extract_fields(self._crew, ctx.raw_text, self._fields_cfg)

        # Step 3b: categorize (deterministic keyword match).
        category, ambiguous = categorize_with_text(
            bill, ctx.raw_text, self._categories_cfg
        )
        bill.category = category
        if ambiguous:
            bill.flag("multiple categories matched")
        if category == self._categories_cfg.default_category:
            bill.flag("no category matched")

        ctx.bill = bill

        # Steps 4 & 5: move the file, append the month CSV.
        ctx.final_path = move_bill(ctx.source_path, bill, self.state.output_root)
        append_csv(bill, self.state.output_root, ctx.final_path.name)
        ctx.status = "done"

        if bill.needs_review:
            logger.warning(
                "Bill filed but needs review (%s): %s",
                ", ".join(bill.review_reasons),
                ctx.final_path.name,
            )

    def _quarantine(self, ctx: BillContext) -> None:
        """Move a failed bill to the archive, ignoring move errors."""
        try:
            if ctx.source_path.exists():
                ctx.final_path = quarantine_bill(ctx.source_path, self.state.archive_dir)
        except OSError as exc:
            logger.error("Could not quarantine %s: %s", ctx.source_path.name, exc)


def _safe_hash(path: Path) -> str:
    try:
        return file_hash(path)
    except OSError:
        return ""
