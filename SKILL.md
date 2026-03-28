---
name: session-analyzer
description: Analyze Claude Code and Codex session logs from JSONL files or date-based log collections, and report tool usage, skill usage, token usage, hourly activity, slow turns, errors, and wait times. Use when the user wants to inspect an agent session, summarize what happened on a given date, compare Claude vs Codex work patterns, or debug workflow/tool behavior from session logs.
---

# Session Analyzer

Analyze Claude Code or Codex session logs with the bundled scripts in `scripts/`.

## Prefer The Auto Entry Script

Use `scripts/analyze_agent_sessions.py` by default.

- With no arguments, it auto-detects Claude or Codex and analyzes today's logs.
- With a date such as `2026-03-20`, it auto-detects which source to use for that day.
- With a file or directory path, it infers the source from the path and log format.
- Override detection only when needed with `--source claude` or `--source codex`.

## Other Entry Scripts

- Use `scripts/analyze_session.py` for Claude-only debugging.
- Use `scripts/analyze_codex_sessions.py` for Codex-only debugging.

## Commands

```bash
cd $HOME/.codex/skills/session-analyzer/scripts
python analyze_agent_sessions.py
python analyze_agent_sessions.py 2026-03-20
python analyze_agent_sessions.py /path/to/session.jsonl
python analyze_agent_sessions.py /path/to/session-dir
python analyze_agent_sessions.py --source claude 2026-03-20
python analyze_agent_sessions.py --source codex 2026-03-20
```

## Source Detection Rules

- For date input, compare available Claude and Codex logs for that day and choose the source with usable data. If both exist, prefer the one with the newer latest update.
- For file input, inspect the first JSON event and fall back to path heuristics such as `~/.claude/projects` and `~/.codex/sessions`.
- For directory input, inspect contained `.jsonl` files when the path alone is ambiguous.
- For Codex single-file paths, analyze the parent session directory.

## What The Report Shows

- Tool call counts, duration totals, averages, and error counts
- Tool category rollups
- Skill invocation counts derived from log contents
- Token usage totals
- Hourly activity histogram
- Slowest turns
- Error summary
- Wait time between turns

## Working Notes

- Prefer the auto entry unless the user explicitly wants only Claude or only Codex.
- If the user asks for a specific day, pass the day directly instead of manually collecting files.
- If a path is missing, run the appropriate script and surface its error message.
- When running the bundled Python scripts for the user, show the Python execution result verbatim by default instead of summarizing it. Summarize only if the user explicitly asks for a summary or if the output is too large to present safely in one response.
- If the user wants behavior changes, keep shared report logic in `session_analysis_core.py` and keep source-specific parsing in the adapter modules.

## Validation

```bash
cd $HOME/.codex/skills/session-analyzer/scripts
python -m compileall analyze_agent_sessions.py analyze_session.py analyze_codex_sessions.py claude_session_adapter.py codex_session_adapter.py session_analysis_core.py
python analyze_agent_sessions.py
python analyze_agent_sessions.py 2026-03-20
python $HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py $HOME/.codex/skills/session-analyzer
```
