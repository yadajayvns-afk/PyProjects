"""CLI entrypoint -- run the bill organizer over the drop folder once.

Usage:
    uv run python main.py [--drop DIR] [--output DIR] [-v]

Processes every new bill in the drop folder, then exits.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

from bill_organizer  import ConfigError, load_categories_config, load_fields_config
from bill_organizer  import BillFlow


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Organize bills from a drop folder.")
    parser.add_argument(
        "--drop", 
        type=Path, 
        default=Path("drop_bills"), 
        help="Folder to scan for new bills."
    )
    parser.add_argument(
        "--output", 
        type=Path, 
        default=Path("output"), 
        help="Root folder for sorted bills."
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=Path("archive/failed"),
        help="Folder for bills that could not be read.",
    )
    parser.add_argument(
        "-v", 
        "--verbose", 
        action="store_true", 
        help="Verbose logging."
    )

    return parser.parse_args(argv)


def _force_utf8_console() -> None:
    """Make stdout/stderr UTF-8 so CrewAI's emoji output doesn't crash on Windows."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    """Run one pass of the bill organizer. Returns a process exit code."""
    _force_utf8_console()
    args = _parse_args(argv)
    load_dotenv()  # picks up OPENROUTER_API_KEY etc. from .env

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(message)s",
    )
    log = logging.getLogger("bill_organizer")

    # Validate config up front so a typo fails before any LLM call.
    try:
        fields_cfg = load_fields_config()
        categories_cfg = load_categories_config()
    except ConfigError as exc:
        log.error("Configuration error:\n%s", exc)
        return 2

    args.drop.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    args.archive.mkdir(parents=True, exist_ok=True)

    flow = BillFlow(
        drop_dir=args.drop,
        output_root=args.output,
        archive_dir=args.archive,
        fields_cfg=fields_cfg,
        categories_cfg=categories_cfg,
    )
    summary = flow.kickoff()
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
