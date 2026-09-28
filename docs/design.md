# 設計

## レイヤ

| Layer | Owner | 内容 |
| --- | --- | --- |
| 0 | nanokit | OS/CLI/dotfiles/MCP/runtime/base config |
| 1 | agent-profile | 個人共通 instructions / Skills / Claude subagents |
| 2 | 各 project repo | team-shared project truth |
| 3 | agent-profile projects/ | private project overlay |
| 4 | local state | attachment / ownership / hash / drift |

## 所有権

同じ live path を nanokit と agent-profile の双方で管理しない。`agent-sync` は foreign path を上書きせず conflict にする。

Claude Code の共通 instructions は `~/.claude/rules/` の個別ファイルとして追加する。これにより nanokit 管理の `~/.claude/CLAUDE.md` を触らない。

Codex には Claude の user-level rules と同等の additive user instruction file を前提にしない。`agent-attach` が project 単位で `AGENTS.override.md` を composite 生成する。

## Codex composite

`AGENTS.override.md` は同じ directory の `AGENTS.md` より優先されるため、private delta だけを書くと project instructions が消える。そこで次の順に合成する。

```text
project AGENTS.md (fallback: CLAUDE.md)
agent-profile/instructions/common.md
agent-profile/instructions/codex.md
projects/<key>/instructions.md
projects/<key>/codex.md
```

nested directory の `AGENTS.md` は Codex 自身の階層探索に任せる。

## Claude local overlay

Claude Code は project `CLAUDE.md` と `CLAUDE.local.md` を加算して読むため、`CLAUDE.local.md` には private project delta だけを書く。共通ルールは user-level rules から供給する。

## Worktree

`CLAUDE.local.md` と `AGENTS.override.md` は worktree ごとの working tree に必要なので全既存 worktree に生成する。一方、Git exclude は `git rev-parse --git-common-dir` から共通 `info/exclude` を更新する。

## Skill

共通 Skill は source を `skills/` に一度だけ持ち、user scope へ個別 symlink する。project-private Skill は Docker/remote/worktree の可搬性を優先し、project working tree へ copy する。

同名 Skill の暗黙上書きは避ける。user scope の衝突は error、project scope の意図的 specialization は対象 project 側で明示的に管理する。

## State

`~/.local/state/agent-profile/` に以下を保存する。

```text
managed.json       global managed path -> source/hash
attachments.json   repo -> worktrees/generated paths/hash
```

prune/detach は state で所有権を確認できるものだけを削除する。

## Detach と settings.local.json

`CLAUDE.local.md`、`AGENTS.override.md`、project-private Skill/agent は ownership marker を確認して削除する。`.claude/settings.local.json` は Claude Code 自身の permission approval などと共有されるため、detach 時にファイル全体を削除しない。profile の設定値を完全に巻き戻したい場合は値単位の provenance を state に保存する拡張を行う。
