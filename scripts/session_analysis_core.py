#!/usr/bin/env python3
"""
セッション分析の共通集計と表示処理。
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime


def parse_timestamp(ts_str: str) -> datetime:
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))


def estimate_content_size(content) -> int:
    if isinstance(content, str):
        return len(content)
    if isinstance(content, list):
        return sum(estimate_content_size(item) for item in content)
    if isinstance(content, dict):
        return sum(estimate_content_size(value) for value in content.values())
    return 0


def merge_turns(all_turns: list[list[dict]]) -> list[dict]:
    merged = [turn for turns in all_turns for turn in turns]
    merged.sort(key=lambda turn: turn["start"])
    return merged


def merge_skill_calls(skill_call_lists: list[list[dict]]) -> list[dict]:
    merged = [call for calls in skill_call_lists for call in calls]
    merged.sort(key=lambda call: call["start"])
    return merged


def canonical_usage(
    *,
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_output_tokens: int = 0,
    total_tokens: int | None = None,
) -> dict:
    if total_tokens is None:
        total_tokens = (
            input_tokens + cached_input_tokens + output_tokens + reasoning_output_tokens
        )
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


def print_tool_stats(turns: list[dict], classify_tool):
    all_tools = []
    tool_durations = defaultdict(list)
    tool_errors = Counter()

    for turn in turns:
        for tool_call in turn["tool_calls"]:
            all_tools.append(tool_call["name"])
            if tool_call["end"]:
                start_ts = parse_timestamp(tool_call["start"])
                end_ts = parse_timestamp(tool_call["end"])
                tool_durations[tool_call["name"]].append(
                    (end_ts - start_ts).total_seconds()
                )
            if tool_call["error"]:
                tool_errors[tool_call["name"]] += 1

    print(f"\n📊 ツール呼び出し統計 (計 {len(all_tools)} 回)")
    print("-" * 50)
    counts = Counter(all_tools)
    for name, count in counts.most_common():
        pct = count / len(all_tools) * 100 if all_tools else 0
        durations = tool_durations.get(name, [])
        avg = sum(durations) / len(durations) if durations else 0
        total = sum(durations)
        errors = tool_errors.get(name, 0)
        err_str = f" ⚠️ {errors}errors" if errors else ""
        print(
            f"  {name:24s} {count:4d}回 ({pct:5.1f}%)  "
            f"平均{avg:6.1f}s  合計{total:7.1f}s{err_str}"
        )

    print("\n📂 カテゴリ別")
    print("-" * 50)
    cat_counts = Counter(classify_tool(name) for name in all_tools)
    cat_durations = defaultdict(float)
    for name, durations in tool_durations.items():
        cat_durations[classify_tool(name)] += sum(durations)
    for category, count in cat_counts.most_common():
        print(
            f"  {category:15s} {count:4d}回  合計{cat_durations.get(category, 0):7.1f}s"
        )

    return tool_errors, len(all_tools)


def print_skill_stats(skill_calls: list[dict]):
    print(f"\n🧩 Skill 呼び出し統計 (計 {len(skill_calls)} 回)")
    print("-" * 50)
    if not skill_calls:
        print("  SKILL.md の読み込みは検出されませんでした")
        return

    skill_counts = Counter(call["skill"] for call in skill_calls)
    skill_errors = Counter(call["skill"] for call in skill_calls if call["error"])
    skill_durations = defaultdict(list)

    for call in skill_calls:
        if not call["end"]:
            continue
        start_ts = parse_timestamp(call["start"])
        end_ts = parse_timestamp(call["end"])
        skill_durations[call["skill"]].append((end_ts - start_ts).total_seconds())

    for name, count in skill_counts.most_common():
        pct = count / len(skill_calls) * 100 if skill_calls else 0
        durations = skill_durations.get(name, [])
        avg = sum(durations) / len(durations) if durations else 0
        total = sum(durations)
        errors = skill_errors.get(name, 0)
        err_str = f" ⚠️ {errors}errors" if errors else ""
        print(
            f"  {name:24s} {count:4d}回 ({pct:5.1f}%)  "
            f"平均{avg:6.1f}s  合計{total:7.1f}s{err_str}"
        )


def print_token_stats(total_usage: dict):
    print("\n🔤 トークン使用量")
    print("-" * 50)
    print(f"  入力:         {total_usage.get('input_tokens', 0):>12,} tokens")
    print(
        f"  キャッシュ:   {total_usage.get('cached_input_tokens', 0):>12,} tokens"
    )
    print(f"  出力:         {total_usage.get('output_tokens', 0):>12,} tokens")
    print(
        f"  推論出力:     {total_usage.get('reasoning_output_tokens', 0):>12,} tokens"
    )
    print(f"  合計:         {total_usage.get('total_tokens', 0):>12,} tokens")


def print_hourly_stats(turns: list[dict]):
    print("\n🕐 時間帯別ツール呼び出し")
    print("-" * 50)
    hour_counts = Counter()
    for turn in turns:
        for tool_call in turn["tool_calls"]:
            hour_counts[parse_timestamp(tool_call["start"]).hour] += 1

    for hour in range(24):
        count = hour_counts.get(hour, 0)
        if count:
            print(f"  {hour:02d}:00  {count:3d} {'█' * (count // 2)}")


def print_slowest_turns(turns: list[dict]):
    print("\n🐌 最も時間がかかったターン TOP10")
    print("-" * 50)
    ranking = []
    for index, turn in enumerate(turns, 1):
        start_ts = parse_timestamp(turn["start"])
        end_ts = parse_timestamp(turn["end"])
        ranking.append(
            (
                (end_ts - start_ts).total_seconds(),
                index,
                [tool["name"] for tool in turn["tool_calls"]],
            )
        )
    ranking.sort(reverse=True)
    for duration, index, tools in ranking[:10]:
        if tools:
            counts = Counter(tools)
            tool_parts = []
            for name, count in counts.most_common(4):
                suffix = f" x{count}" if count > 1 else ""
                tool_parts.append(f"{name}{suffix}")
            shown = sum(count for _, count in counts.most_common(4))
            omitted = sum(counts.values()) - shown
            if omitted > 0:
                tool_parts.append(f"... +{omitted}")
            tool_str = ", ".join(tool_parts)
        else:
            tool_str = "(thinking)"
        print(f"  Turn {index:3d}: {duration:7.1f}s  [{tool_str}]")


def print_error_stats(tool_errors: Counter, total_tools: int, skill_calls: list[dict]):
    total_errors = sum(tool_errors.values())
    total_skill_errors = sum(1 for call in skill_calls if call["error"])
    error_rate = (total_errors / total_tools * 100) if total_tools else 0

    print("\n❌ エラー統計")
    print("-" * 50)
    print(f"  エラー数: {total_errors} / {total_tools} ({error_rate:.1f}%)")
    for name, count in tool_errors.most_common():
        print(f"    {name}: {count}回")
    print(f"  Skillエラー数: {total_skill_errors} / {len(skill_calls)}")


def print_wait_stats(turns: list[dict]):
    print("\n⏱️ ターン間待機時間 (ユーザー思考時間)")
    print("-" * 50)
    waits = []
    for prev, curr in zip(turns, turns[1:]):
        wait = (
            parse_timestamp(curr["start"]) - parse_timestamp(prev["end"])
        ).total_seconds()
        if 0 < wait < 3600:
            waits.append(wait)

    if not waits:
        print("  待機時間は検出されませんでした")
        return

    ordered = sorted(waits)
    print(f"  平均: {sum(waits) / len(waits):.1f}s")
    print(f"  中央値: {ordered[len(ordered) // 2]:.1f}s")
    print(f"  最大: {max(waits):.1f}s")
    print(f"  合計待機: {sum(waits) / 60:.1f}分")


def print_report(
    *,
    title: str,
    summary_lines: list[str],
    event_total: int,
    turns: list[dict],
    skill_calls: list[dict],
    total_usage: dict,
    classify_tool,
):
    print("=" * 60)
    print(title)
    for line in summary_lines:
        print(line)
    print(f"イベント数: {event_total}")
    print(f"ターン数: {len(turns)}")
    print("=" * 60)

    tool_errors, total_tools = print_tool_stats(turns, classify_tool)
    print_skill_stats(skill_calls)
    print_token_stats(total_usage)
    print_hourly_stats(turns)
    print_slowest_turns(turns)
    print_error_stats(tool_errors, total_tools, skill_calls)
    print_wait_stats(turns)
