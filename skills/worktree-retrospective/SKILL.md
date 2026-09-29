---
name: worktree-retrospective
description: "worktree / branch の成果を docs/<worktree-name>/YYYY-MM-DD-hhmm.md に記録として残すときに使う。merge、push、PR 作成、branch 削除、worktree 削除を指示されたら、それを実行する前に必ずこの skill を通す。最終的な設計だけでなく、ユーザーとのやりとりの経緯と、なぜその決定に至ったか（却下した案を含む）を残す。「マージして」「push して」「PR を作って」「worktree 消して」「branch 削除して」「片付けて」などが該当する。"
user-invocable: true
---

# Worktree Retrospective

worktree の成果がその worktree の外に出る / 失われる瞬間に、経緯ごと `docs/` へ残すための手順。

## 発動条件

いずれも **実行する前に** この skill を通す。記録を残さずに merge / push / 削除をしない。

| 契機 | ユーザーの言い方の例 |
|---|---|
| merge | 「main に取り込んで」「マージして」 |
| push / PR 作成 | 「push して」「PR を作って」 |
| branch / worktree 削除 | 「worktree 消して」「branch 削除して」「片付けて」 |

## 出力先

```
docs/<worktree-name>/YYYY-MM-DD-hhmm.md
```

`<worktree-name>` は agent 名（`.claude/worktrees/<agent-name>` の末尾）。`hhmm` は記録を書く時点の
時・分（24 時間表記、ホストのローカル時刻）。例: `docs/impl-camera-path/2026-09-07-1432.md`。

```bash
date '+%Y-%m-%d-%H%M'
```

分まで入れるのは、同じ worktree で同じ日に merge → push → 削除と契機が続いても、契機ごとに
独立した記録を残せるようにするため。`YYYY-MM-DD.md` 形式の古い記録がある場合はそのまま読む。
rename はしない。

**どの checkout に書くかは契機で変える。** branch の運命が違うため。

| 契機 | 書き込み先 | 理由 |
|---|---|---|
| merge / push / PR | **worktree 側**。`docs:` commit にして変更と一緒に載せる | branch が生きているので、記録が実装と同じ commit 列で main に届く |
| merge せず削除 | **primary checkout 側**。現在の branch で commit | worktree 側に書くと削除の道連れになる |

**内容を重複させない。** 契機ごとに新しい file を作る（同日でも追記しない）。既に記録がある
worktree で 2 回目以降を書くときは、前の記録に書いたことを繰り返さず、差分だけを書いて冒頭で
`- **前の記録**: [2026-09-08-1631.md](2026-09-08-1631.md)` のように link する。削除の記録なら
最終状態（削除日、最終 SHA、削除理由）が主題になる。

## 手順

### 1. 対象の確認

```bash
git -C .claude/worktrees/<name> branch --show-current
git -C .claude/worktrees/<name> log --oneline main..HEAD
git -C .claude/worktrees/<name> diff --stat main...HEAD
git -C .claude/worktrees/<name> rev-parse HEAD
```

tip の SHA は必ず控える。branch 削除後も reflog から辿れる期間（既定で約 90 日）の保険になる。

### 2. 経緯の洗い出し

**ここがこのドキュメントの主目的。** 最終形だけを書くと価値が半減する。会話を遡って次を拾う。

- ユーザーが最初に何を求めたか。途中で要求がどう変わったか。
- agent が出した案と、ユーザーがどれを選んだか。**選ばなかった案と、選ばなかった理由。**
- 実装中に判明した制約（環境、依存、性能、既存コードの前提）と、それが設計をどう変えたか。
- 行き止まりになった試行と、なぜ行き止まりだったか。

「なぜ今この形なのか」を、次に読む人が再構成できる粒度で書く。

### 3. 検証と証跡の突き合わせ

- 実行した検証と結果を集める。証跡の表は `agent-work-report` skill と同じ書式にする。
- `reports/<name>/` に HTML レポートがあれば参照を書く。**`reports/` は gitignore されているので、リポジトリには残らない**旨も添える。
- worktree 内にしかない証跡で残す価値があるものは、削除前に primary checkout 側へ退避する。

### 4. 執筆

`templates/retrospective.md` をひな型にする。節を勝手に減らさない。書くことがない節は「該当なし」と明記する。

### 5. ユーザー確認

書き終えたら、**経緯の節に書き漏らしがないかユーザーに確認する。** agent の側からは見えていない意図（なぜその要求をしたか）が抜けやすい。

### 6. commit

```bash
git add docs/<name>/$(date '+%Y-%m-%d-%H%M').md
git commit -m "docs: record <name> worktree retrospective"
```

commit してから、本来指示された merge / push / 削除に進む。

## 注意

- この skill は記録を書くところまで。merge / push / 削除そのものは `merge-worktree` skill や `scripts/remove_agent_worktree.sh` が担当する。
- branch 削除を伴う場合、記録の commit が **削除対象の branch にしか無い** 状態で削除しない。上の表のとおり書き込み先を選ぶ。
