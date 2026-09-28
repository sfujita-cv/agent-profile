# Claude Code 追加ルール

- project の `CLAUDE.md` / `.claude/CLAUDE.md` / `CLAUDE.local.md` を優先して、そのリポジトリ固有の実行方法に従う。
- subagent は役割分離に意味がある場合だけ使い、単純な作業を不要に分割しない。
- project-local の秘密でない個人設定は `CLAUDE.local.md` または `.claude/settings.local.json` に置き、team-shared policy と混在させない。
- Skill が該当する場合は長い手順を再発明せず Skill を読み、そのワークフローに従う。
