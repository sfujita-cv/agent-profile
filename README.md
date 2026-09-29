# agent-profile

Claude Code / Codex を複数リポジトリで使うための、個人向けエージェント設定の Source of Truth です。

このリポジトリは次の責務だけを持ちます。

- 複数プロジェクトで共通化したい個人ルール（`instructions/`）
- Claude Code / Codex の双方で使う Agent Skills（`skills/`）
- Claude Code の subagent 定義（`agents/claude/`）
- 上記を user scope へ安全に配布する `agent-sync` と、診断用の `agent-doctor`

OS/CLI/dotfiles/MCP/Claude Code 本体設定/Codex 本体設定の bootstrap は nanokit 側の責務とし、このリポジトリから既存の nanokit 管理ファイルを上書きしません。プロジェクトごとに設定を切り替える仕組みは持ちません。

> [!IMPORTANT]
> このリポジトリは public として公開する前提です。API キー、トークン、パスワードなどの秘密情報は置きません。

## 収録している内容

内容は、agent worktree と per-agent container で開発する複数のリポジトリの `CLAUDE.md` と `.claude/` を統合したものです。特定のリポジトリに固有のコマンドや設定は含めず、どのリポジトリにも通用する形に一般化しています。

### instructions

| ファイル | 配布先 | 内容 |
| --- | --- | --- |
| `common.md` | `~/.claude/rules/90-agent-profile-common.md` | 言語方針、agent worktree ワークフロー、Pixi / Docker / submodule 方針、作業報告、検証方針など |
| `claude.md` | `~/.claude/rules/91-agent-profile-claude.md` | Claude Code 固有の補足 |
| `codex.md` | 自動配布なし | Codex 固有の補足（nanokit overlay provider 実装後に配布する想定） |

### Skills

| Skill | 内容 |
| --- | --- |
| `agent-work-report` | 再現コマンドと根拠出力の所在を含む作業報告の書式 |
| `code-review-etiquette` | actionable なレビューコメントの書き方と指摘の優先順位 |
| `create-pr` | 直近の commit から日本語のドラフト PR を作る（script 同梱） |
| `git-commits` | commit の粒度とメッセージ構造 |
| `merge-worktree` | agent worktree を論理単位で commit し、main へ merge して片付ける（script 同梱） |
| `phased-plan` | cross-model review 前提のフェーズ分割実装計画を `plans/` に書く |
| `python-cv-implementation` | shape / dtype / device / 座標系 / 単位を扱う CV・3D 実装規約 |
| `pytorch-debugging` | NaN・OOM・device / shape mismatch・DataLoader・性能の切り分け手順 |
| `readme-four-questions` | 4 つの問いで README を構成する |
| `verification-report-html` | 検証結果の HTML レポートを組み立て、実ブラウザで検査して Artifact で渡す（script・skeleton 同梱） |
| `worktree-retrospective` | merge / push / 削除の前に経緯ごと記録を残す（テンプレート同梱） |

nanokit に同名の Skill がある `ai-code-changes` と `code-comments` は中身がほぼ同じなので取り込まず、nanokit 版を使います。nanokit の `plan` / `readme-writing` とは中身が別物の Skill は、`phased-plan` / `readme-four-questions` という別名にしています。

同梱 script は `~/.claude/skills/<name>/scripts/...`（Codex では `~/.agents/skills/<name>/scripts/...`）で呼び出す前提に書き換えています。リポジトリ側に同名の project Skill がある場合は、そちらが優先されます。

### Claude subagents

| agent | 内容 |
| --- | --- |
| `code-reviewer` | diff / worktree の変更を読み、重大度順に指摘する read-only のレビュー担当 |
| `worktree-debugger` | worktree と per-agent container で再現・切り分け・最小修正を行う |
| `worktree-implementer` | worktree と per-agent container で小さく安全な実装を行う |

いずれも `memory: project` なので、agent memory は各リポジトリの `.claude/agent-memory/` に書かれます。nanokit にも `code-reviewer.md` があり名前が衝突するため、subagent は既定では配布しません。

## セットアップ

Python 3.11 以上と Git だけを使います。追加パッケージのインストールは不要です。

```bash
git clone git@github.com:sfujita-cv/agent-profile.git ~/src/agent-profile
cd ~/src/agent-profile

./bin/agent-sync --dry-run
./bin/agent-sync
./bin/agent-doctor
```

`agent-sync` は既定で次を symlink で配布します。

```text
<clone 先>              -> ~/.config/agent-profile/current   (stable path)
instructions/common.md  -> ~/.claude/rules/90-agent-profile-common.md
instructions/claude.md  -> ~/.claude/rules/91-agent-profile-claude.md
skills/<name>/          -> ~/.claude/skills/<name>
skills/<name>/          -> ~/.agents/skills/<name>
```

所有権のルールは次の通りです。

- 配布先が存在しなければ作成します。
- 以前このプロファイルが作った symlink（`~/.local/state/agent-profile/managed.json` に記録）は、clone を移動して壊れていても張り直します。
- それ以外のファイル・symlink・symlink された親ディレクトリ（例: `~/.claude/skills -> nanokit`）は上書きせず conflict として報告します。1 件 conflict があっても、安全な項目は処理を続けます。
- プロファイルから消した Skill は `stale` と表示され、`--prune` を付けたときだけ削除されます。削除するのは記録と一致する symlink だけです。

nanokit が管理している `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、`~/.claude/settings.json`、`~/.codex/config.toml` は触りません。`profile.toml` の `[global]` で配布対象を切り替えられます。subagent も配布する場合は次を実行します。

```bash
./bin/agent-sync --include-agents
```

Codex には、Claude の `~/.claude/rules/` のように追加で読ませる user instruction の置き場がありません。そのため `instructions/` は現状 Claude にだけ届き、Codex には Skill だけが届きます。

### 終了コード

| code | 意味 |
| --- | --- |
| 0 | 成功、または差分なし |
| 1 | 設定ファイルの欠落・破損など致命的エラー |
| 2 | conflict、または `--check` で差分あり |

## agent-doctor

```bash
./bin/agent-doctor                       # 構造検証 + agent 名の衝突警告 + agent-sync --check
./bin/agent-doctor --skills              # 構造検証だけ
./bin/agent-doctor --inventory ~/work/x  # x/.claude/skills と agent-profile / nanokit の Skill を name + hash で比較
```

`--inventory` は、同名 Skill が同一内容なら重複削除の候補、内容が違えば specialization か片方への同期の候補、リポジトリにしかなければ取り込み候補、agent-profile と nanokit の user scope で名前が重なればエラー、として表示します。

## nanokit との連携

- nanokit: `~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、Claude/Codex runtime 設定、nanokit 自身の Skill と agent
- agent-profile: `~/.claude/rules/` の個人ルール、名前が衝突しない Skill、stable path

nanokit の `agent-config-sync` は自分が作っていない symlink を消さないため、この境界で共存できます。将来 nanokit 側に overlay provider を実装する場合の契約案を [`integrations/nanokit/README.md`](integrations/nanokit/README.md) に記載しています。

詳細は [`docs/design.md`](docs/design.md) を参照してください。

## 検証

```bash
python3 -m unittest discover -s tests -v
./bin/agent-doctor
```
