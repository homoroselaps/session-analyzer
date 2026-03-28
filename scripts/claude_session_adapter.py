#!/usr/bin/env python3
"""
Claude Code セッションログを共通分析構造へ変換する。
"""

from __future__ import annotations

from datetime import date, datetime
import json
import sys
from pathlib import Path

from session_analysis_core import (
    canonical_usage,
    estimate_content_size,
    merge_skill_calls,
    merge_turns,
    parse_timestamp,
)


def classify_tool(name: str) -> str:
    categories = {
        "file_read": ["Read", "Glob", "Grep"],
        "file_write": ["Write", "Edit"],
        "shell": ["Bash"],
        "web": ["WebSearch", "WebFetch"],
        "agent": ["Agent", "TaskOutput"],
        "system": [
            "ToolSearch",
            "EnterPlanMode",
            "ExitPlanMode",
            "AskUserQuestion",
            "NotebookEdit",
        ],
    }
    for category, tools in categories.items():
        if name in tools:
            return category
    return "other"


def load_events(path: Path) -> list[dict]:
    events = []
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"  skip line {line_no}: invalid JSON", file=sys.stderr)
    events.sort(key=lambda event: event.get("timestamp", ""))
    return events


def build_turns(events: list[dict]) -> list[dict]:
    turns = []
    current_turn = None

    for event in events:
        event_type = event.get("type")
        ts = event.get("timestamp")
        if not ts:
            continue

        if event_type == "user":
            message = event.get("message", {})
            content = message.get("content", "")
            if isinstance(content, list) and current_turn:
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        tool_use_id = item.get("tool_use_id", "")
                        for tool_call in reversed(current_turn["tool_calls"]):
                            if tool_call["id"] != tool_use_id:
                                continue
                            tool_call["end"] = ts
                            tool_call["output_size"] = estimate_content_size(
                                item.get("content", "")
                            )
                            if item.get("is_error"):
                                tool_call["error"] = True
                            break

            if current_turn:
                turns.append(current_turn)
            current_turn = {
                "start": ts,
                "end": ts,
                "user_content_size": estimate_content_size(content),
                "tool_calls": [],
                "total_input_tokens": 0,
                "total_output_tokens": 0,
                "cache_read_tokens": 0,
            }
            continue

        if event_type == "assistant" and current_turn:
            current_turn["end"] = ts
            message = event.get("message", {})
            usage = message.get("usage", {})
            current_turn["total_input_tokens"] += usage.get("input_tokens", 0)
            current_turn["total_output_tokens"] += usage.get("output_tokens", 0)
            current_turn["cache_read_tokens"] += usage.get(
                "cache_read_input_tokens", 0
            )

            for item in message.get("content", []):
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    current_turn["tool_calls"].append(
                        {
                            "id": item.get("id", ""),
                            "name": item.get("name", "unknown"),
                            "start": ts,
                            "end": None,
                            "input_size": estimate_content_size(item.get("input", {})),
                            "output_size": 0,
                            "error": False,
                        }
                    )
            continue

        if event_type == "tool_result" and current_turn:
            tool_use_id = event.get("toolUseID") or event.get("tool_use_id")
            for tool_call in reversed(current_turn["tool_calls"]):
                if tool_call["id"] != tool_use_id:
                    continue
                tool_call["end"] = ts
                tool_call["output_size"] = estimate_content_size(event.get("content", ""))
                if event.get("is_error"):
                    tool_call["error"] = True
                break
            continue

        if event_type == "progress" and current_turn:
            current_turn["end"] = ts

    if current_turn:
        turns.append(current_turn)

    return turns


def walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_dicts(child)
    elif isinstance(value, list):
        for item in value:
            yield from walk_dicts(item)


def extract_skill_name(tool_use: dict) -> str | None:
    if tool_use.get("type") != "tool_use" or tool_use.get("name") != "Read":
        return None

    tool_input = tool_use.get("input", {})
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str):
        return None

    skill_path = Path(file_path)
    if skill_path.name != "SKILL.md":
        return None
    return skill_path.parent.name or None


def collect_skill_calls(events: list[dict]) -> list[dict]:
    skill_calls = []
    skill_calls_by_id = {}

    for event in events:
        ts = event.get("timestamp")
        if not ts:
            continue

        if event.get("type") == "tool_result":
            tool_use_id = event.get("toolUseID") or event.get("tool_use_id")
            if tool_use_id in skill_calls_by_id:
                skill_calls_by_id[tool_use_id]["end"] = ts
                if event.get("is_error"):
                    skill_calls_by_id[tool_use_id]["error"] = True

        for node in walk_dicts(event):
            if node.get("type") == "tool_use":
                skill_name = extract_skill_name(node)
                tool_use_id = node.get("id")
                if not skill_name or not tool_use_id or tool_use_id in skill_calls_by_id:
                    continue

                record = {
                    "id": tool_use_id,
                    "skill": skill_name,
                    "start": ts,
                    "end": None,
                    "error": False,
                }
                skill_calls.append(record)
                skill_calls_by_id[tool_use_id] = record

            elif node.get("type") == "tool_result":
                tool_use_id = node.get("tool_use_id") or node.get("toolUseID")
                if tool_use_id in skill_calls_by_id:
                    skill_calls_by_id[tool_use_id]["end"] = ts
                    if node.get("is_error"):
                        skill_calls_by_id[tool_use_id]["error"] = True

    return skill_calls


def build_usage(turns: list[dict]) -> dict:
    input_tokens = sum(turn["total_input_tokens"] for turn in turns)
    output_tokens = sum(turn["total_output_tokens"] for turn in turns)
    cached_input_tokens = sum(turn.get("cache_read_tokens", 0) for turn in turns)
    return canonical_usage(
        input_tokens=input_tokens,
        cached_input_tokens=cached_input_tokens,
        output_tokens=output_tokens,
        reasoning_output_tokens=0,
    )


def parse_target_arg(raw: str | None) -> tuple[str, Path | None]:
    base = Path.home() / ".claude" / "projects"
    if not raw:
        today = date.today()
        return today.isoformat(), None

    raw = raw.strip()
    candidate = Path(raw).expanduser()
    if candidate.exists():
        return candidate.name, candidate

    normalized = raw.replace("/", "-")
    dt = datetime.strptime(normalized, "%Y-%m-%d").date()
    return dt.isoformat(), None


def find_session_files_for_date(target_date: date) -> list[Path]:
    base = Path.home() / ".claude" / "projects"
    return sorted(
        (
            path
            for path in base.rglob("*.jsonl")
            if datetime.fromtimestamp(path.stat().st_mtime).date() == target_date
        ),
        key=lambda path: path.stat().st_mtime,
    )


def analyze_session_file(session_path: Path) -> dict:
    events = load_events(session_path)
    turns = build_turns(events)
    skill_calls = collect_skill_calls(events)
    all_ts = [event.get("timestamp") for event in events if event.get("timestamp")]
    start = parse_timestamp(min(all_ts))
    end = parse_timestamp(max(all_ts))
    return {
        "event_total": len(events),
        "turns": turns,
        "skill_calls": skill_calls,
        "total_usage": build_usage(turns),
        "summary_lines": [
            f"セッション分析: {session_path.stem[:8]}...",
            f"期間: {start:%Y-%m-%d %H:%M} ~ {end:%Y-%m-%d %H:%M}",
            f"総時間: {end - start}",
        ],
    }


def analyze_files(target_label: str, session_files: list[Path]) -> dict:
    if not session_files:
        raise FileNotFoundError(f"No session logs found for {target_label}")

    if len(session_files) == 1:
        return analyze_session_file(session_files[0])

    event_total = 0
    all_turns = []
    all_skill_calls = []

    for session_file in session_files:
        events = load_events(session_file)
        event_total += len(events)
        all_turns.append(build_turns(events))
        all_skill_calls.append(collect_skill_calls(events))

    turns = merge_turns(all_turns)
    skill_calls = merge_skill_calls(all_skill_calls)
    turn_timestamps = [parse_timestamp(turn["start"]) for turn in turns] + [
        parse_timestamp(turn["end"]) for turn in turns
    ]
    start_ts = min(turn_timestamps)
    end_ts = max(turn_timestamps)

    return {
        "event_total": event_total,
        "turns": turns,
        "skill_calls": skill_calls,
        "total_usage": build_usage(turns),
        "summary_lines": [
            f"Claude セッション分析: {target_label}",
            f"セッション数: {len(session_files)}",
            f"期間: {start_ts:%Y-%m-%d %H:%M} ~ {end_ts:%Y-%m-%d %H:%M}",
            f"総時間: {end_ts - start_ts}",
        ],
    }
