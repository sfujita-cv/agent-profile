# nanokit integration

## 現在の運用

nanokit を base writer、agent-profile を additive overlay として共存させる。

agent-profile は次を直接変更しない。

- `~/.claude/CLAUDE.md`
- `~/.codex/AGENTS.md`
- `~/.claude/settings.json`
- `~/.codex/config.toml`

Claude 共通指示は `~/.claude/rules/90-agent-profile-common.md` などへ追加する。Skill は名前単位で ownership を判定する。

## 将来の provider 契約案

nanokit が overlay provider を実装した後は、live user config の writer を nanokit 1つへ寄せる。

`90-agent-profile.toml.example` はその契約案であり、現行 nanokit が自動で読むことを前提にしない。`root` に書く `~/.config/agent-profile/current` は、`agent-sync` が clone 先への symlink として張る stable path である。

Provider の基本規則:

- instructions は provider priority 順に明示結合する。
- Skill 名が重複した場合は既定で error にする。
- override は provider manifest で明示された場合だけ許可する。
- settings は key 単位 merge、security-sensitive key は restrictive merge を優先する。
