# agent-profile 開発方針

## 目的

このリポジトリは Claude Code / Codex の個人共通設定と project-local overlay を安全に管理するためのテンプレートである。

## 言語

- README、設計書、ユーザー向け説明は日本語で記述する。
- コードの識別子、ログキー、コードコメントは英語で記述する。

## 実装原則

- Python 3.11+ の標準ライブラリだけを使う。
- 既存ファイルを無条件に上書きしない。所有権を証明できないパスは conflict にする。
- `rm -rf`、force push などの破壊的操作を自動化しない。
- nanokit 管理ファイルを agent-profile 側から直接置換しない。
- project-local 生成物は Git tracked file を上書きしない。
- Docker/remote/worktree を考慮し、project-local overlay は絶対パス symlink に依存しない。
- 変更後は `python3 -m unittest discover -s tests -v` を実行する。

## Skill

Skill は `skills/<name>/SKILL.md` に置く。`name` とディレクトリ名を一致させ、description に発火条件を明記する。一般的な常識を長文で繰り返さず、再利用価値がある具体的なワークフローだけを置く。

## 変更範囲

プロジェクト固有の GPU、Docker、Pixi、E2E、デプロイ手順をこのリポジトリへ吸い上げない。それらは対象リポジトリの `CLAUDE.md` / `AGENTS.md` / project Skill が所有する。
