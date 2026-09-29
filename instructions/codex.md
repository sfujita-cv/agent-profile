# Codex 追加ルール

- repository の `AGENTS.md` を project truth として扱う。
- project-local Skill（`.agents/skills/` や `.claude/skills/`）がある場合は、user scope の Skill より対象リポジトリの具体的なコマンド・制約を優先する。
- 実装・レビュー・デバッグの結果には、実際に確認した差分と、実行した検証コマンドとその結果を結び付ける。
