# agent-profile

Claude Code / Codex を複数リポジトリで使うための、個人向けエージェント設定の Source of Truth です。

このリポジトリは次の責務だけを持ちます。

- 複数プロジェクトで共通化したい個人ルール
- Claude Code / Codex の双方で使う Agent Skills
- Claude Code の個人 subagent 定義
- プロジェクト固有だが Git 管理したくない local overlay
- 上記を安全に配布する `agent-sync` / `agent-attach` / `agent-doctor`

OS/CLI/dotfiles/MCP/Claude Code 本体設定/Codex 本体設定の bootstrap は nanokit 側の責務とし、このリポジトリから既存の nanokit 管理ファイルを上書きしません。

> [!IMPORTANT]
> このリポジトリを個人用ルールや非公開プロジェクトの overlay 保管先として使う場合は、GitHub リポジトリ自体を **private** にしてください。API キー、トークン、パスワードなどの秘密情報は private repository にも保存しません。

## アーキテクチャ

```text
nanokit
  └─ runtime / dotfiles / MCP / base Claude+Codex config

agent-profile
  ├─ instructions/       個人共通ルール
  ├─ skills/             Claude/Codex 共通 Skill source
  ├─ agents/claude/      Claude user-level subagent source
  ├─ projects/           repo-specific private overlay source
  └─ bin/                sync / attach / doctor

project repository
  ├─ CLAUDE.md            team-shared project truth
  ├─ AGENTS.md            team-shared project truth
  ├─ CLAUDE.local.md      generated personal overlay
  └─ AGENTS.override.md   generated composite for Codex
```

原則は「最大限共通化する」ではなく、**1つのポリシーに1つの所有者を割り当てる**ことです。GPU ID、Docker Compose、Pixi、E2E テストコマンド、デプロイ手順などは対象リポジトリ側に残します。

詳細は [`docs/design.md`](docs/design.md) を参照してください。

## セットアップ

Python 3.11 以上と Git だけを使います。追加パッケージのインストールは不要です。

```bash
git clone git@github.com:sfujita-cv/agent-profile.git ~/src/agent-profile
cd ~/src/agent-profile

./bin/agent-sync --dry-run
./bin/agent-sync
./bin/agent-doctor
```

`agent-sync` は既定で次を配布します。

```text
instructions/common.md  -> ~/.claude/rules/90-agent-profile-common.md
instructions/claude.md  -> ~/.claude/rules/91-agent-profile-claude.md
skills/<name>/          -> ~/.claude/skills/<name>
skills/<name>/          -> ~/.agents/skills/<name>
```

既存パスがこのリポジトリ以外に所有されている場合は上書きせず conflict として報告します。特に nanokit が管理している `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、`~/.claude/settings.json`、`~/.codex/config.toml` は触りません。

Claude subagent は nanokit の管理方式と衝突する可能性があるため既定では配布しません。必要な場合だけ次を実行します。

```bash
./bin/agent-sync --include-agents
```

## プロジェクトへの attach

対象リポジトリで次を実行します。

```bash
~/src/agent-profile/bin/agent-attach .
```

`origin` を正規化して `projects/<owner>__<repo>/` を探索します。該当プロファイルがなくても Codex 用の共通 composite は生成できます。

Claude Code 側は user-level rules で共通ルールを読み込み、プロジェクト固有の private 指示だけを `CLAUDE.local.md` に生成します。Codex は `AGENTS.override.md` が同階層の `AGENTS.md` を置換する仕様のため、次を合成した実ファイルを生成します。

1. 対象リポジトリの `AGENTS.md`。なければ `CLAUDE.md`
2. `instructions/common.md`
3. `instructions/codex.md`
4. `projects/<owner>__<repo>/instructions.md`
5. `projects/<owner>__<repo>/codex.md`

絶対パス symlink は Docker / remote / worktree で壊れやすいため、project overlay は symlink ではなく生成コピーにします。

```bash
agent-attach --status .
agent-attach --refresh .
agent-attach --detach .
```

複数 worktree がある場合は既存 worktree を列挙して同じ overlay を配置します。除外設定は `.gitignore` を変更せず、Git common dir の `info/exclude` に管理ブロックを追加します。

## プロジェクトプロファイル

`projects/example/` をコピーして作成します。

```text
projects/acme__vision-engine/
├── project.toml
├── instructions.md
├── claude.md
├── codex.md
├── claude/
│   └── settings.local.json
├── skills/
└── agents/
```

`project.toml` の `match.remotes` はディレクトリ名ではなく Git remote を基準にします。SSH/HTTPS は同一リポジトリとして正規化されます。

## nanokit との連携

現状の安全な境界は次です。

- nanokit: `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、Claude/Codex runtime 設定
- agent-profile: user-level Claude rules、名前衝突しない Skill、project local overlay

将来 nanokit 側に overlay provider を実装する場合の契約案を [`integrations/nanokit/README.md`](integrations/nanokit/README.md) に記載しています。最終形では live user config の writer を nanokit 1つに寄せる想定です。

## 検証

```bash
python3 -m unittest discover -s tests -v
./bin/agent-doctor
```

`agent-doctor` は構造、Skill metadata、重複名、broken symlink、attach drift、tracked local overlay などを検査します。
