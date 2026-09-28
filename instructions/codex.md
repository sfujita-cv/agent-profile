# Codex 追加ルール

- repository の `AGENTS.md` を project truth として扱う。
- `AGENTS.override.md` は local overlay のために生成される composite であり、元の project guidance を失わないようにする。
- project-local Skill がある場合は generic Skill より対象リポジトリの具体的なコマンド・制約を優先する。
- 実装・レビュー・デバッグの結果には、実際に確認した差分と検証コマンドを結び付ける。
