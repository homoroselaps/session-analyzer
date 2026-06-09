#!/usr/bin/env python3
"""
Analyze Codex session logs (.jsonl) by date.
"""

from __future__ import annotations

import argparse
import sys

from codex_session_adapter import (
    analyze_date_directory,
    classify_tool,
    parse_date_arg,
)
from session_analysis_core import print_report


def main():
    parser = argparse.ArgumentParser(description="Analyze Codex session logs by date")
    parser.add_argument(
        "date",
        nargs="?",
        help="Date to analyze (YYYY-MM-DD or YYYY/MM/DD) or a direct session directory path",
    )
    args = parser.parse_args()

    date_label, session_dir = parse_date_arg(args.date)
    try:
        report = analyze_date_directory(date_label, session_dir)
    except FileNotFoundError:
        print(f"Session log not found: {session_dir}", file=sys.stderr)
        sys.exit(1)

    print_report(
        title=report["title"],
        summary_lines=report["summary_lines"],
        event_total=report["event_total"],
        turns=report["turns"],
        skill_calls=report["skill_calls"],
        total_usage=report["total_usage"],
        classify_tool=classify_tool,
    )


if __name__ == "__main__":
    main()
