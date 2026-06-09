<h1 align="center">Session Analyzer</h1>

<p align="center">
  A Skill that automatically analyzes Claude Code and Codex session logs
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB.svg" alt="Python">
  <img src="https://img.shields.io/badge/Claude%20Code-supported-black.svg" alt="Claude Code">
  <img src="https://img.shields.io/badge/Codex-supported-0A7B83.svg" alt="Codex">
  <img src="https://img.shields.io/badge/Logs-JSONL-555.svg" alt="JSONL">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/document-English-white.svg" alt="English doc"/>
</p>

Reads Claude Code and Codex session logs and returns a text report describing what happened.

## 📊 What You Get

This Skill produces a consolidated analysis report with:

- How many sessions, turns, and events occurred that day
- Which tools were used and how often
- Which Skills were called
- How many tokens were consumed
- Which hours had the most activity
- Which turns were slowest
- Where errors occurred
- How much wait time elapsed between turns

The output is a plain text report like this:

```text
============================================================
Codex session analysis: 2026-03-25
Target directory: ~/.codex/sessions/2026/03/25
Session count: 2
Period: 2026-03-24 21:50 ~ 2026-03-24 22:22
Total time: 0:32:23.832000
Events: 475
Turns: 15
============================================================

Tool call statistics
By category
Skill call statistics
Token usage
Tool calls by hour
Top 10 slowest turns
Error statistics
Wait time between turns
```

As a rule, return the Python output itself to the user. Do not reduce it to a summary unless the user explicitly asks for one.

## 🚀 Usage

Invoke it as `$session-analyzer` by default.

- `Analyze today's sessions`
- `Analyze the logs for 2026-03-20`
- `Analyze this jsonl: /path/to/session.jsonl`
- `Analyze this directory: /path/to/session-dir`

## ✨ Capabilities

- Auto-detect Claude Code or Codex
- Analyze today's logs automatically
- Analyze logs for a specific date
- Analyze a single `jsonl` file or a directory

## 🔍 Auto-Detection Rules

- For date input, the analyzer searches for Claude and Codex logs available on that day.
- If both exist, the source with the newer modification time wins.
- For file input, the source is inferred from the first event and the path.
- For directory input, the source is inferred from the contained `.jsonl` files.
- For a single Codex file, analysis runs at the parent directory level.

## 📁 File Layout

- `scripts/analyze_agent_sessions.py`
  - Shared auto-detect entrypoint
- `scripts/claude_session_adapter.py`
  - Claude log adapter
- `scripts/codex_session_adapter.py`
  - Codex log adapter
- `scripts/session_analysis_core.py`
  - Shared aggregation and rendering logic

## 🧪 Validation

```bash
cd ~/.codex/skills/session-analyzer/scripts
python -m compileall analyze_agent_sessions.py analyze_session.py analyze_codex_sessions.py claude_session_adapter.py codex_session_adapter.py session_analysis_core.py
python analyze_agent_sessions.py
python analyze_agent_sessions.py 2026-03-20
python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/session-analyzer
```
