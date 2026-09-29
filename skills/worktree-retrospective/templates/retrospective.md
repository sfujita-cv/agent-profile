# <worktree-name>: <一行で何をしたか>

- **worktree**: `.claude/worktrees/<name>`
- **branch**: `agent/<name>`
- **記録時刻**: YYYY-MM-DD hh:mm (file 名の `YYYY-MM-DD-hhmm` と揃える)
- **前の記録**: 同じ worktree の前の記録への相対 link / 無ければ「なし」
- **期間**: YYYY-MM-DD 〜 YYYY-MM-DD
- **最終 commit**: `<SHA>`
- **結末**: merge 済み / push 済み (PR #NN) / merge せず破棄

## 1. 概要

何をした worktree か 2-3 文。結論を先に書く。

## 2. 背景と目的

なぜこの作業が必要だったか。解こうとした問題。着手時点で分かっていたことと、分かっていなかったこと。

## 3. やりとりの経緯と意思決定

**この節がこのドキュメントの主目的。** 最終形だけでなく、そこに至る過程を残す。

### 3.1 経緯

時系列で、要求 → 検討 → 決定の流れを書く。

| 時点 | ユーザーの要求 / 判明した事実 | agent の提案 | 決定 |
|---|---|---|---|
| | | | |

### 3.2 採用しなかった案

**必ず書く。** 次に同じ問題を見た人が同じ道を再探索しないために残す。

| 案 | 却下した理由 |
|---|---|
| | |

### 3.3 行き止まりだった試行

試して駄目だったこと。何が起きて、なぜ駄目だったか。該当なしならそう書く。

## 4. 最終的な設計 / 実装

変更したモジュールと責務。設計上の要点。なぜその構造にしたか（3 節の決定と対応させる）。

## 5. 差分の記録

```
branch: agent/<name>
tip:    <SHA>
```

```
$ git log --oneline main..agent/<name>
```

```
$ git diff --stat main...agent/<name>
```

branch 削除後も、上の SHA から reflog 経由で約 90 日は復元できる。

## 6. 検証と根拠出力

実行した検証と、その根拠となった出力。書式は `agent-work-report` skill に合わせる。

| 出力 | path | 何を示すか | 生成コマンド |
|---|---|---|---|
| | | | |

未実行のまま残した検証があれば、ここに理由付きで書く。

HTML レポート: `reports/<name>/YYYY-MM-DD_<topic>.html`
（`reports/` は gitignore されているためリポジトリには含まれない。必要なら再生成する）

## 7. 再現コマンド

リポジトリの `CLAUDE.md` の作業報告の節と `agent-work-report` skill に合わせて書く。

```bash
# worktree 作成
scripts/create_agent_worktree.sh <name>

# 検証実行 (-- 以降は worktree root で実行される)
scripts/enter_agent_container.sh <name> -- <検証コマンド>
```

branch 削除後に追試する場合は、上の SHA を checkout してから実行する。

## 8. 残課題 / 引き継ぎ

やり残したこと、既知の制約、次に手を付けるならどこか。
