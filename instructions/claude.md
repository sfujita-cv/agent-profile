# Claude Code 追加ルール

- project の `CLAUDE.md` / `.claude/CLAUDE.md` / `CLAUDE.local.md` を読み、そのリポジトリ固有の実行方法に従う。
- subagent は役割分離に意味がある場合（独立した調査の並列化、レビューの第二視点、長い探索結果の要約）だけ使い、単純な作業を不要に分割しない。
- subagent に委譲するときは、目的、変更してよい範囲、期待する検証コマンドを渡す。subagent の報告は検証済みの事実と推測を区別して受け取る。
- project scope に同名の Skill や agent がある場合は project 側が specialization なので、user scope の版より優先する。
- 秘密でない個人設定は `CLAUDE.local.md` または `.claude/settings.local.json` に置き、team-shared な `.claude/settings.json` と混在させない。
- Skill が該当する場合は長い手順を再発明せず Skill を読み、そのワークフローに従う。
