# 設計

## レイヤ

| Layer | Owner | 内容 |
| --- | --- | --- |
| 0 | nanokit | OS/CLI/dotfiles/MCP/runtime/base config |
| 1 | agent-profile | 個人共通 instructions / Skills / Claude subagents |
| 2 | 各 project repo | team-shared project truth（`CLAUDE.md` / `AGENTS.md` / project Skill） |
| 3 | local state | ownership / hash / drift |

当初はこの間に「agent-profile の private project overlay（`projects/`、`agent-attach` による `CLAUDE.local.md` / `AGENTS.override.md` の生成）」の層を置いていた。リポジトリを public で公開する方針に変えたため、2026-09-28 にこの層ごと廃止した。プロジェクトごとの調整は各リポジトリの `CLAUDE.md` / project Skill が担う。

## 取り込み方針

既存リポジトリの `CLAUDE.md`・Skill・agent を参考にするが、取り込むのはどのリポジトリにも通用する統合版だけにする。

- 特定のリポジトリ名、そのリポジトリにしか無いコマンド・環境変数・path・データ名・実験名は書かない。リポジトリ間で違う記述は併記せず、一般化して 1 つにまとめる。一般化すると中身が残らないもの（特定データセットの準備手順など）は取り込まない。
- `instructions/common.md` は `~/.claude/rules/` から全プロジェクトの全セッションで読み込まれるため、リポジトリをまたいで通用する方針だけを置く。具体的な値（GPU 番号、環境変数名、検証コマンド）は各リポジトリの `CLAUDE.md` に任せる。
- nanokit に同名 Skill がある場合、中身がほぼ同じなら取り込まずに nanokit 版を使い、中身が別物なら改名して取り込む（`phased-plan`、`readme-four-questions`）。
- Skill に同梱した script は user scope の `~/.claude/skills/<name>/scripts/...` から呼び出す前提で書く。リポジトリ側に同名の project Skill がある場合はそちらが優先される。

## 所有権

同じ live path を nanokit と agent-profile の双方で管理しない。`agent-sync` は foreign path を上書きせず conflict にする。

`agent-sync` が変更してよいのは次の 3 種類だけである。

1. 存在しない配布先（作成）
2. すでに agent-profile の source を指している symlink（何もしない）
3. `managed.json` に記録した link 文字列と一致する symlink（clone の移動などで壊れたものを relink）

配布先の親ディレクトリが symlink の場合（例: `~/.claude/skills -> ~/nanokit/...`）も conflict とする。そのまま書くと他ツールの repository の中にファイルを作ってしまうためである。

nanokit の `agent-config-sync` は自分が作っていない symlink を削除しないので、名前が衝突しない限り両者は同じディレクトリに共存できる。なお設計初期は `~/.claude/agents` が nanokit ディレクトリへの symlink である前提だったが、2026-09-28 時点のこのマシンでは実ディレクトリの中に個別 symlink が並ぶ形だった。どちらの形でも上記の規則で安全側に倒れる。ただし nanokit 由来の `code-reviewer.md` と名前が衝突するため、global agent の配布は既定で無効のままにしている。

## Stable path

`agent-sync` は `~/.config/agent-profile/current` を clone 先への symlink として張る。将来の nanokit overlay provider など外部ツールは、clone 先ではなくこの path を参照する。

## Instructions の配布先

Claude Code の共通 instructions は `~/.claude/rules/` の個別ファイルとして追加する。これにより nanokit 管理の `~/.claude/CLAUDE.md` を触らない。

Codex には Claude の user-level rules と同等の追加用 instruction file が無い。`~/.codex/AGENTS.md` は nanokit が所有しているため、現状 `instructions/` は Codex に配布しない。Codex へ届けるのは nanokit overlay provider（`integrations/nanokit/`）の実装後とする。

## Skill

共通 Skill は source を `skills/` に一度だけ持ち、user scope（`~/.claude/skills/` と `~/.agents/skills/`）へ個別 symlink する。ディレクトリ全体を symlink にしないのは、nanokit や plugin が同じディレクトリを使うためである。

同名 Skill の暗黙上書きは避ける。user scope の衝突は conflict、project scope の同名 Skill は意図的な specialization とみなす。

## State

`~/.local/state/agent-profile/managed.json` に、配布先 path → source / 種別 / hash を保存する。`--prune` は、ここに記録された link 文字列と一致する symlink だけを削除する。
