<h1 align="center">Session Analyzer</h1>

<p align="center">
  Claude Code と Codex のセッションログを自動判定で分析する Skill
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-3776AB.svg" alt="Python">
  <img src="https://img.shields.io/badge/Claude%20Code-supported-black.svg" alt="Claude Code">
  <img src="https://img.shields.io/badge/Codex-supported-0A7B83.svg" alt="Codex">
  <img src="https://img.shields.io/badge/Logs-JSONL-555.svg" alt="JSONL">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/document-日本語-white.svg" alt="JA doc"/>
</p>

Claude Code と Codex のセッションログを読み取り、何が起きたかをテキストレポートとして返します。

## 📊 ユーザが受け取るもの

この Skill を使うと、次のような情報がまとまった分析レポートを受け取れます。

- その日に何セッション・何ターン・何イベントあったか
- どのツールを何回使ったか
- どの Skill が呼ばれたか
- トークンをどれくらい消費したか
- 何時台に処理が集中したか
- どのターンが遅かったか
- どこでエラーが出たか
- ターン間でどれくらい待機時間があったか

返却形式は、次のようなテキストレポートです。

```text
============================================================
Codex セッション分析: 2026-03-25
対象ディレクトリ: ~/.codex/sessions/2026/03/25
セッション数: 2
期間: 2026-03-24 21:50 ~ 2026-03-24 22:22
総時間: 0:32:23.832000
イベント数: 475
ターン数: 15
============================================================

📊 ツール呼び出し統計
📂 カテゴリ別
🧩 Skill 呼び出し統計
🔤 トークン使用量
🕐 時間帯別ツール呼び出し
🐌 最も時間がかかったターン TOP10
❌ エラー統計
⏱️ ターン間待機時間
```

原則として、ユーザには Python の実行結果そのものを返します。要約だけで済ませず、分析レポート全文を見せる前提です。

## 🚀 使い方

基本は `$session-analyzer` として呼びます。

- `今日のセッションを分析して`
- `2026-03-20 のログを分析して`
- `この jsonl を分析して: /path/to/session.jsonl`
- `このディレクトリを分析して: /path/to/session-dir`

## ✨ できること

- Claude Code / Codex の自動判定
- 当日ログの自動分析
- 日付指定での分析
- 単一 `jsonl` ファイル、またはディレクトリ指定での分析

## 🔍 自動判定のルール

- 日付指定では、その日に使える Claude / Codex ログを探します。
- 両方ある場合は、より新しい更新時刻を持つ方を優先します。
- ファイル指定では、先頭イベントの形式とパスからソースを判定します。
- ディレクトリ指定では、含まれる `.jsonl` を見てソースを判定します。
- Codex の単一ファイルを渡した場合は、親ディレクトリ単位で分析します。

## 📁 ファイル構成

- `scripts/analyze_agent_sessions.py`
  - 自動判定付きの共通入口
- `scripts/claude_session_adapter.py`
  - Claude ログの変換
- `scripts/codex_session_adapter.py`
  - Codex ログの変換
- `scripts/session_analysis_core.py`
  - 共通の集計・表示ロジック

## 🧪 検証

```bash
cd ~/.codex/skills/session-analyzer/scripts
python -m compileall analyze_agent_sessions.py analyze_session.py analyze_codex_sessions.py claude_session_adapter.py codex_session_adapter.py session_analysis_core.py
python analyze_agent_sessions.py
python analyze_agent_sessions.py 2026-03-20
python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/session-analyzer
```
