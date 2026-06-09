#!/usr/bin/env python3
"""
Extract analysis data from Claude Code session logs.
Read JSONL directly and render the shared report format.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import sys
from pathlib import Path

from claude_session_adapter import (
    analyze_files,
    analyze_session_file,
    classify_tool,
    find_session_files_for_date,
    parse_target_arg,
)
from session_analysis_core import print_report


def analyze_path(session_path: Path):
    report = analyze_session_file(session_path)
    print_report(
        title=report["summary_lines"][0],
        summary_lines=report["summary_lines"][1:],
        event_total=report["event_total"],
        turns=report["turns"],
        skill_calls=report["skill_calls"],
        total_usage=report["total_usage"],
        classify_tool=classify_tool,
    )


def analyze_target(raw_target: str | None):
    target_label, target_path = parse_target_arg(raw_target)
    if target_path is not None:
        if target_path.is_file():
            analyze_path(target_path)
            return

        session_files = sorted(target_path.rglob("*.jsonl"))
        report = analyze_files(target_label, session_files)
    else:
        target_date = datetime.strptime(target_label, "%Y-%m-%d").date()
        session_files = find_session_files_for_date(target_date)
        report = analyze_files(target_label, session_files)

    print_report(
        title=report["summary_lines"][0],
        summary_lines=report["summary_lines"][1:],
        event_total=report["event_total"],
        turns=report["turns"],
        skill_calls=report["skill_calls"],
        total_usage=report["total_usage"],
        classify_tool=classify_tool,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze Claude session logs by file, directory, or updated date"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Session file, directory, or date (YYYY-MM-DD / YYYY/MM/DD)",
    )
    args = parser.parse_args()

    try:
        analyze_target(args.target)
    except FileNotFoundError as exc:
        print(
            f"Session log not found: {exc.filename or args.target}",
            file=sys.stderr,
        )
        sys.exit(1)
