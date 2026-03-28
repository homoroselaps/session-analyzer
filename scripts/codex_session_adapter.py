#!/usr/bin/env python3
"""
Codex セッションログを共通分析構造へ変換する。
"""

from __future__ import annotations

import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from session_analysis_core import (
    canonical_usage,
    estimate_content_size,
    merge_skill_calls,
    merge_turns,
    parse_timestamp,
)


SKILL_PATH_PATTERN = re.compile(
    r"(?P<path>(?:/[^\s\"']+)?(?:^|(?<=\s)|(?<=[\"']))(?:[^\s\"']+/)?SKILL\.md)"
)


def parse_date_arg(raw: str | None) -> tuple[str, Path]:
    base = Path.home() / ".codex" / "sessions"
    if not raw:
        today = date.today()
        return today.isoformat(), base / f"{today:%Y/%m/%d}"

    raw = raw.strip()
    candidate = Path(raw).expanduser()
    if candidate.exists():
        return candidate.name, candidate

    normalized = raw.replace("/", "-")
    dt = datetime.strptime(normalized, "%Y-%m-%d").date()
    return dt.isoformat(), base / f"{dt:%Y/%m/%d}"


def classify_tool(name: str) -> str:
    if name.startswith("web_search."):
        return "web"
    if name in {"exec_command", "write_stdin"}:
        return "shell"
    if name == "apply_patch":
        return "file_write"
    if name.startswith("mcp__serena__"):
        if any(
            token in name
            for token in (
                "write_memory",
                "edit_memory",
                "delete_memory",
                "rename_memory",
            )
        ):
            return "memory_write"
        return "code_intel"
    if name.startswith("mcp__"):
        return "mcp"
    if name in {
        "spawn_agent",
        "send_input",
        "wait_agent",
        "resume_agent",
        "close_agent",
    }:
        return "agent"
    if name == "parallel":
        return "system"
    return "other"


def parse_tool_arguments(raw: str) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def find_skill_names(text: str, workdir: str | None = None) -> set[str]:
    if not text:
        return set()

    skills = set()
    for match in SKILL_PATH_PATTERN.finditer(text):
        raw_path = match.group("path")
        if not raw_path:
            continue

        path = Path(raw_path)
        if not path.is_absolute() and workdir:
            path = Path(workdir) / path

        if path.name != "SKILL.md":
            continue

        parent = path.parent.name
        if parent:
            skills.add(parent)
    return skills


def extract_skill_names_from_call(tool_name: str, arguments: dict) -> set[str]:
    skills = set()
    workdir = arguments.get("workdir")

    for key in ("cmd", "arguments", "uri", "path", "file_path"):
        value = arguments.get(key)
        if isinstance(value, str):
            skills.update(find_skill_names(value, workdir))

    if tool_name.startswith("mcp__"):
        for value in arguments.values():
            if isinstance(value, str):
                skills.update(find_skill_names(value, workdir))

    return skills


def normalize_output_text(output) -> str:
    if isinstance(output, str):
        return output
    try:
        return json.dumps(output, ensure_ascii=False)
    except TypeError:
        return str(output)


def is_tool_error(tool_name: str, output) -> bool:
    lowered = normalize_output_text(output).lower()
    return (
        f"{tool_name} failed:" in lowered
        or "sandbox(denied" in lowered
        or "process exited with code 1" in lowered
        or "process exited with code 2" in lowered
        or "process exited with code 126" in lowered
        or "process exited with code 127" in lowered
        or "error:" in lowered
    )


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
                print(f"skip line {line_no}: invalid JSON in {path}", file=sys.stderr)
    events.sort(key=lambda item: item.get("timestamp", ""))
    return events


def build_turns(events: list[dict]) -> tuple[list[dict], list[dict], dict]:
    turns = []
    current_turn = None
    pending_calls = {}
    web_search_index = 0
    skill_calls = []
    latest_total_usage = {}

    def ensure_turn(ts: str) -> dict:
        nonlocal current_turn
        if current_turn is None:
            current_turn = {
                "start": ts,
                "end": ts,
                "user_content_size": 0,
                "tool_calls": [],
            }
        return current_turn

    def close_turn(ts: str | None = None):
        nonlocal current_turn
        if current_turn is None:
            return
        if ts:
            current_turn["end"] = ts
        turns.append(current_turn)
        current_turn = None

    for event in events:
        ts = event.get("timestamp")
        if not ts:
            continue

        ev_type = event.get("type")
        payload = event.get("payload", {})

        if ev_type == "turn_context":
            current_turn = {
                "start": ts,
                "end": ts,
                "user_content_size": 0,
                "tool_calls": [],
            }
            continue

        if ev_type == "event_msg" and payload.get("type") == "task_started":
            close_turn(ts)
            current_turn = {
                "start": ts,
                "end": ts,
                "user_content_size": 0,
                "tool_calls": [],
            }
            continue

        if ev_type == "event_msg" and payload.get("type") in {
            "task_complete",
            "turn_aborted",
        }:
            ensure_turn(ts)["end"] = ts
            close_turn(ts)
            continue

        if ev_type == "event_msg" and payload.get("type") == "token_count":
            info = payload.get("info") or {}
            latest_total_usage = info.get("total_token_usage", {}) or latest_total_usage
            if current_turn:
                current_turn["end"] = ts
            continue

        if ev_type != "response_item":
            if current_turn:
                current_turn["end"] = ts
            continue

        item_type = payload.get("type")
        turn = ensure_turn(ts)
        turn["end"] = ts

        if item_type == "message":
            if payload.get("role") == "user":
                turn["user_content_size"] += estimate_content_size(
                    payload.get("content", [])
                )

        elif item_type == "function_call":
            tool_name = payload.get("name", "unknown")
            call_id = payload.get("call_id", "")
            arguments = parse_tool_arguments(payload.get("arguments", ""))
            tool_call = {
                "id": call_id,
                "name": tool_name,
                "start": ts,
                "end": None,
                "input_size": estimate_content_size(arguments),
                "output_size": 0,
                "error": False,
            }
            turn["tool_calls"].append(tool_call)
            if call_id:
                pending_calls[call_id] = tool_call

            for skill_name in extract_skill_names_from_call(tool_name, arguments):
                skill_calls.append(
                    {
                        "id": call_id or f"skill-{len(skill_calls) + 1}",
                        "skill": skill_name,
                        "start": ts,
                        "end": None,
                        "error": False,
                    }
                )

        elif item_type == "function_call_output":
            call_id = payload.get("call_id", "")
            output = payload.get("output", "")
            tool_call = pending_calls.get(call_id)
            if tool_call:
                tool_call["end"] = ts
                tool_call["output_size"] = estimate_content_size(output)
                tool_call["error"] = is_tool_error(tool_call["name"], output)

                for skill_call in reversed(skill_calls):
                    if skill_call["id"] == call_id and skill_call["end"] is None:
                        skill_call["end"] = ts
                        skill_call["error"] = tool_call["error"]
                        break

        elif item_type == "web_search_call":
            action = payload.get("action", {})
            action_type = action.get("type", "unknown")
            web_search_index += 1
            turn["tool_calls"].append(
                {
                    "id": f"web-{web_search_index}",
                    "name": f"web_search.{action_type}",
                    "start": ts,
                    "end": ts,
                    "input_size": estimate_content_size(action),
                    "output_size": 0,
                    "error": payload.get("status")
                    not in {"completed", "succeeded", None},
                }
            )

    close_turn()
    return turns, skill_calls, latest_total_usage


def build_usage(total_usage: dict) -> dict:
    return canonical_usage(
        input_tokens=total_usage.get("input_tokens", 0),
        cached_input_tokens=total_usage.get("cached_input_tokens", 0),
        output_tokens=total_usage.get("output_tokens", 0),
        reasoning_output_tokens=total_usage.get("reasoning_output_tokens", 0),
        total_tokens=total_usage.get("total_tokens", 0),
    )


def analyze_date_directory(date_label: str, session_dir: Path) -> dict:
    session_files = sorted(session_dir.rglob("*.jsonl"))
    if not session_files:
        raise FileNotFoundError(f"No session logs found under {session_dir}")

    event_total = 0
    all_turns = []
    all_skill_calls = []
    latest_usage = {}

    for session_file in session_files:
        events = load_events(session_file)
        turns, skill_calls, usage = build_turns(events)
        event_total += len(events)
        all_turns.append(turns)
        all_skill_calls.append(skill_calls)
        if usage:
            latest_usage = usage

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
        "total_usage": build_usage(latest_usage),
        "summary_lines": [
            f"対象ディレクトリ: {session_dir}",
            f"セッション数: {len(session_files)}",
            f"期間: {start_ts:%Y-%m-%d %H:%M} ~ {end_ts:%Y-%m-%d %H:%M}",
            f"総時間: {end_ts - start_ts}",
        ],
        "title": f"Codex セッション分析: {date_label}",
    }
