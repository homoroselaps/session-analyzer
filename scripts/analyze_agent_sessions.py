#!/usr/bin/env python3
"""
Claude Code / Codex のセッションログを自動判定して分析する。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from claude_session_adapter import (
    analyze_files as analyze_claude_files,
    analyze_session_file as analyze_claude_session_file,
    classify_tool as classify_claude_tool,
    find_session_files_for_date as find_claude_session_files_for_date,
)
from codex_session_adapter import (
    analyze_date_directory as analyze_codex_date_directory,
    classify_tool as classify_codex_tool,
)
from session_analysis_core import print_report


def parse_target_date(raw_target: str | None) -> date:
    if not raw_target:
        return date.today()
    normalized = raw_target.strip().replace("/", "-")
    return datetime.strptime(normalized, "%Y-%m-%d").date()


def find_codex_session_dir_for_date(target_date: date) -> Path | None:
    session_dir = Path.home() / ".codex" / "sessions" / f"{target_date:%Y/%m/%d}"
    return session_dir if session_dir.exists() else None


def latest_mtime(paths: list[Path]) -> float:
    return max((path.stat().st_mtime for path in paths), default=0.0)


def looks_like_codex_session(path: Path) -> bool:
    return ".codex" in path.parts or "sessions" in path.parts


def looks_like_claude_session(path: Path) -> bool:
    return ".claude" in path.parts or "projects" in path.parts


def detect_source_from_file(session_file: Path) -> str:
    try:
        with session_file.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                event_type = event.get("type")
                if event_type in {"user", "assistant", "tool_result", "progress"}:
                    return "claude"
                if event_type in {"turn_context", "event_msg", "response_item"}:
                    return "codex"
                break
    except (OSError, json.JSONDecodeError):
        pass

    if looks_like_claude_session(session_file):
        return "claude"
    if looks_like_codex_session(session_file):
        return "codex"
    raise FileNotFoundError(f"Could not detect source for {session_file}")


def detect_source_from_path(target_path: Path) -> str:
    if target_path.is_file():
        return detect_source_from_file(target_path)

    if looks_like_codex_session(target_path):
        return "codex"
    if looks_like_claude_session(target_path):
        return "claude"

    session_files = sorted(target_path.rglob("*.jsonl"))
    if not session_files:
        raise FileNotFoundError(f"No session logs found under {target_path}")
    return detect_source_from_file(session_files[0])


def detect_source_for_date(target_date: date) -> tuple[str, list[Path] | Path]:
    claude_files = find_claude_session_files_for_date(target_date)
    codex_dir = find_codex_session_dir_for_date(target_date)
    codex_files = sorted(codex_dir.rglob("*.jsonl")) if codex_dir else []

    if claude_files and not codex_files:
        return "claude", claude_files
    if codex_files and not claude_files:
        return "codex", codex_dir
    if claude_files and codex_files:
        if latest_mtime(codex_files) >= latest_mtime(claude_files):
            return "codex", codex_dir
        return "claude", claude_files

    raise FileNotFoundError(
        f"No Claude or Codex session logs found for {target_date.isoformat()}"
    )


def run_claude(report: dict):
    print_report(
        title=report["summary_lines"][0],
        summary_lines=report["summary_lines"][1:],
        event_total=report["event_total"],
        turns=report["turns"],
        skill_calls=report["skill_calls"],
        total_usage=report["total_usage"],
        classify_tool=classify_claude_tool,
    )


def run_codex(report: dict):
    print_report(
        title=report["title"],
        summary_lines=report["summary_lines"],
        event_total=report["event_total"],
        turns=report["turns"],
        skill_calls=report["skill_calls"],
        total_usage=report["total_usage"],
        classify_tool=classify_codex_tool,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Claude Code or Codex session logs with source auto-detection"
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Session file, directory, or date (YYYY-MM-DD / YYYY/MM/DD). Defaults to today.",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "claude", "codex"],
        default="auto",
        help="Session source. Defaults to auto.",
    )
    args = parser.parse_args()

    try:
        if args.target:
            candidate = Path(args.target).expanduser()
            if candidate.exists():
                source = args.source
                if source == "auto":
                    source = detect_source_from_path(candidate)

                if source == "claude":
                    if candidate.is_file():
                        run_claude(analyze_claude_session_file(candidate))
                    else:
                        run_claude(
                            analyze_claude_files(
                                candidate.name,
                                sorted(candidate.rglob("*.jsonl")),
                            )
                        )
                else:
                    session_dir = candidate.parent if candidate.is_file() else candidate
                    run_codex(
                        analyze_codex_date_directory(session_dir.name, session_dir)
                    )
                return

        target_date = parse_target_date(args.target)
        source = args.source
        payload: list[Path] | Path

        if source == "auto":
            source, payload = detect_source_for_date(target_date)
        elif source == "claude":
            payload = find_claude_session_files_for_date(target_date)
            if not payload:
                raise FileNotFoundError(
                    f"No Claude session logs found for {target_date.isoformat()}"
                )
        else:
            payload = find_codex_session_dir_for_date(target_date)
            if payload is None:
                raise FileNotFoundError(
                    f"No Codex session logs found for {target_date.isoformat()}"
                )

        if source == "claude":
            run_claude(analyze_claude_files(target_date.isoformat(), payload))
        else:
            run_codex(analyze_codex_date_directory(target_date.isoformat(), payload))
    except FileNotFoundError as exc:
        print(f"セッションログが見つかりません: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
