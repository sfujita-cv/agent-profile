# agent-profile 開発方針

## 目的

このリポジトリは Claude Code / Codex の個人共通設定（instructions、Skills、Claude subagents）を管理し、user scope へ安全に配布する public repository である。

## 言語

- README、設計書、ユーザー向け説明は日本語で記述する。
- コードの識別子、ログキー、コードコメントは英語で記述する。

## 実装原則

- Python 3.11+ の標準ライブラリだけを使う。
- 既存ファイルを無条件に上書きしない。所有権を証明できないパスは conflict にする。
- `rm -rf`、force push などの破壊的操作を自動化しない。
- nanokit 管理ファイルを agent-profile 側から直接置換しない。
- 変更後は `python3 -m unittest discover -s tests -v` を実行する。

## Skill

Skill は `skills/<name>/SKILL.md` に置く。`name` とディレクトリ名を一致させ、description に発火条件を明記する。nanokit に同名の Skill がある場合、中身がほぼ同じなら取り込まず nanokit 版を使い、中身が別物なら別名に改名して取り込む。

## 変更範囲

- プロジェクトごとに設定を切り替える仕組み（project overlay、`CLAUDE.local.md` / `AGENTS.override.md` の生成など）は持たない。
- 既存リポジトリの `CLAUDE.md` や Skill を参考にしてよいが、取り込むのは複数リポジトリに通用する統合版だけにする。特定のリポジトリ名、そのリポジトリにしか無いコマンド・環境変数・path・データ名・実験名は書かない。リポジトリ間で違う記述は、リポジトリ名を付けて併記せず、一般化して 1 つにまとめる。
- public repository なので、API token、認証情報、private key などの秘密情報は置かない。
