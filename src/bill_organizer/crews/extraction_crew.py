"""Step 3a -- the single-agent CrewAI crew that extracts bill fields.

This is the one genuinely "AI" part of the pipeline. It is isolated behind
``extract_fields`` so it could be swapped for a plain LLM call without touching
the Flow.

LLM provider: OpenRouter via litellm. Set ``OPENROUTER_API_KEY`` in ``.env`` and
optionally ``BILL_ORGANIZER_MODEL`` to override the model.
"""

from __future__ import annotations

import logging
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml
from crewai import Agent, Crew, Process, Task
from dateutil import parser as date_parser

from ..config import FieldsConfig
from ..models import ExtractedBill

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).parent / "config"
DEFAULT_MODEL = "openrouter/anthropic/claude-3.5-sonnet"


def _model() -> str:
    return os.getenv("BILL_ORGANIZER_MODEL", DEFAULT_MODEL)


def _load_yaml(name: str) -> dict:
    return yaml.safe_load((_CONFIG_DIR / name).read_text(encoding="utf-8"))


def _field_instructions(fields_cfg: FieldsConfig) -> str:
    """Render the configured fields into a bullet list for the task prompt."""
    lines = []
    for f in fields_cfg.fields:
        req = "REQUIRED" if f.required else "optional"
        lines.append(f"  - {f.name} ({f.type}, {req}): {f.description}")
    return "\n".join(lines)


def build_extraction_crew(fields_cfg: FieldsConfig) -> Crew:
    """Build the single-agent extraction crew, prompt-templated from config.

    The returned crew expects a ``raw_text`` input on ``kickoff``.
    """
    agents_yaml = _load_yaml("agents.yaml")
    tasks_yaml = _load_yaml("tasks.yaml")

    agent = Agent(
        role=agents_yaml["extractor"]["role"],
        goal=agents_yaml["extractor"]["goal"],
        backstory=agents_yaml["extractor"]["backstory"],
        llm=_model(),
        verbose=False,
    )

    task = Task(
        description=tasks_yaml["extract_fields"]["description"].replace(
            "{field_instructions}", _field_instructions(fields_cfg)
        ),
        expected_output=tasks_yaml["extract_fields"]["expected_output"],
        agent=agent,
        output_pydantic=ExtractedBill,
    )

    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def extract_fields(crew: Crew, raw_text: str, fields_cfg: FieldsConfig) -> ExtractedBill:
    """Run the crew on ``raw_text`` and return a cleaned :class:`ExtractedBill`.

    Always returns a bill -- on LLM failure it returns an empty bill flagged
    for review rather than raising.
    """
    try:
        result = crew.kickoff(inputs={"raw_text": raw_text})
    except Exception as exc:  # network / API / parsing failure
        logger.error("Extraction crew failed: %s", exc)
        bill = ExtractedBill()
        bill.flag(f"extraction failed: {exc}")
        return bill

    bill = result.pydantic if getattr(result, "pydantic", None) else ExtractedBill()
    if not isinstance(bill, ExtractedBill):
        bill = ExtractedBill()
        bill.flag("extraction returned no structured output")

    return _post_process(bill, fields_cfg)


def _post_process(bill: ExtractedBill, fields_cfg: FieldsConfig) -> ExtractedBill:
    """Clean amount/date values and flag missing required fields."""
    bill.amount = _clean_amount(bill.amount, fields_cfg)
    bill.bill_date = _clean_date(bill.bill_date)

    for field in fields_cfg.fields:
        if field.required and getattr(bill, field.name, None) in (None, ""):
            bill.flag(f"missing required field: {field.name}")

    return bill


def _clean_amount(amount: object, fields_cfg: FieldsConfig) -> Decimal | None:
    """Strip currency tokens/separators from an amount and coerce to Decimal."""
    if amount is None:
        return None
    if isinstance(amount, Decimal):
        return amount

    text = str(amount)
    for token in fields_cfg.settings.currency_symbol_strip:
        text = text.replace(token, "")
    text = text.strip()
    # Keep digits, sign and a single decimal point only.
    text = re.sub(r"[^0-9.\-]", "", text)
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        logger.warning("Could not parse amount %r", amount)
        return None


def _clean_date(value: object) -> date | None:
    """Parse a possibly-messy date value into a ``date`` (day-first preferred)."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return date_parser.parse(str(value), dayfirst=True).date()
    except (ValueError, OverflowError):
        logger.warning("Could not parse date %r", value)
        return None
