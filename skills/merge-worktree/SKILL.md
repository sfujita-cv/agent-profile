---
name: merge-worktree
description: "agent worktree / git worktree の変更を、論理単位ごとに commit して main に merge し、merge 済み worktree と branch を安全に片付ける必要があるときに使う。例: 「このworktreeをmainに取り込んで」「impl-xxx worktreeをmergeして」「agent worktreeの変更をコミットしてmainへ入れて」。"
user-invocable: true
---

# Merge Worktree

agent worktree の差分を、意味のある commit に分けて main に取り込み、merge 済み worktree と branch を安全に片付けるための workflow です。git 操作はこの skill に同梱した script 経由で行います。

## 基本方針

- 1 commit は 1 つの論理的変更にする。
- commit message は `feat: ...`、`fix: ...`、`docs: ...`、`test: ...`、`chore: ...` など、変更のまとまりが分かるものにする。
- worktree 側の未 commit 差分をすべて確認してから commit する。
- main 側に未 commit 変更がある場合、勝手に上書きしない。必要なら main 側の変更も別 commit にするか、ユーザーに判断を求める。
- merge 後は、worktree branch が main に取り込まれていることを script で確認してから worktree を remove し、branch を `git branch -d` で削除する。

## Script

この skill では、git 操作を次の script に集約します。

```bash
~/.claude/skills/merge-worktree/scripts/inspect_worktree.sh
~/.claude/skills/merge-worktree/scripts/commit_scope.sh
~/.claude/skills/merge-worktree/scripts/merge_into_main.sh
~/.claude/skills/merge-worktree/scripts/cleanup_merged_worktree.sh
```

## Workflow

### 1. 状態確認

main checkout で実行します。

```bash
bash ~/.claude/skills/merge-worktree/scripts/inspect_worktree.sh \
  .claude/worktrees/<worktree-name> \
  .
```

確認すること:

- worktree branch 名。
- worktree 側の modified / untracked files。
- main 側の未 commit 差分。
- worktree が main と同じ repository の worktree であること。

### 2. 論理単位に分割

`inspect_worktree.sh` の出力と必要に応じた diff 確認から、変更を commit 単位に分けます。

例:

- `docs:` README、plan、CLAUDE.md など説明文書。
- `feat:` 新しい package / module / CLI。
- `test:` tests の追加。
- `chore:` Pixi task や package metadata。

### 3. Worktree 側で commit

各まとまりごとに `commit_scope.sh` を呼びます。pathspec は worktree root からの相対 path で指定します。

```bash
bash ~/.claude/skills/merge-worktree/scripts/commit_scope.sh \
  .claude/worktrees/<worktree-name> \
  "feat: add camera path prototype" \
  -- \
  src configs scripts pyproject.toml pixi.toml
```

別のまとまりは別 commit にします。

```bash
bash ~/.claude/skills/merge-worktree/scripts/commit_scope.sh \
  .claude/worktrees/<worktree-name> \
  "test: add synthetic geometry coverage" \
  -- \
  tests
```

### 3.5. Retrospective を書く

merge の前に、この worktree の記録を残します。手順は `~/.claude/skills/worktree-retrospective/SKILL.md` を参照してください。

merge する場合、記録は **worktree 側** に書いて `docs:` commit にします。branch が生きているので、実装と同じ commit 列で main に届きます。

```bash
bash ~/.claude/skills/merge-worktree/scripts/commit_scope.sh \
  .claude/worktrees/<worktree-name> \
  "docs: record <worktree-name> worktree retrospective" \
  -- \
  docs/<worktree-name>
```

最終的な設計だけでなく、ユーザーとのやりとりの経緯と、なぜその決定に至ったか（却下した案を含む）を書きます。

### 4. Main 側を clean にする

merge 前に main checkout の未 commit 差分を確認します。

```bash
bash ~/.claude/skills/merge-worktree/scripts/inspect_worktree.sh \
  .claude/worktrees/<worktree-name> \
  .
```

main 側に関連する変更がある場合は、main 側で commit するか、worktree branch 側へ移すか、ユーザーに確認します。未関連の変更は勝手に revert しません。

### 5. Main に merge

worktree branch の commit が完了し、main 側が clean であることを確認してから merge します。

```bash
bash ~/.claude/skills/merge-worktree/scripts/merge_into_main.sh \
  .claude/worktrees/<worktree-name> \
  .
```

### 6. Merge 済み worktree / branch を削除

merge が成功したら、次の script で worktree を remove してから branch を削除します。

```bash
bash ~/.claude/skills/merge-worktree/scripts/cleanup_merged_worktree.sh \
  .claude/worktrees/<worktree-name> \
  .
```

削除の前に、3.5 の retrospective が `docs/<worktree-name>/` に存在することを確認します。既にあれば、その file に追記するのではなく、新しい `YYYY-MM-DD-hhmm.md` に最終状態（削除日、最終 SHA、削除理由）を書き、冒頭から前の記録へ link します。

この script は次を確認してから削除します。

- worktree と main checkout が同じ repository に属している。
- worktree 側と main 側に未 commit 変更がない。
- worktree branch が main branch の ancestor であり、merge 済みである。
- 削除対象 branch が main branch 自身ではない。

### 7. 検証

cleanup 後に、main checkout でプロジェクトの通常検証を実行します。例:

```bash
docker compose -p verify-<worktree-name> run --rm dev python -m unittest discover -s tests
docker compose -p verify-<worktree-name> down
```

実行した検証だけを報告します。

## 注意

- conflict が出た場合は script が停止します。conflict 内容を読んで、解決方針をユーザーに共有してから進めます。
- branch / worktree 削除は `cleanup_merged_worktree.sh` だけで行います。手作業の `git branch -D` や強制削除は使いません。
- destructive command、reset、checkout による破棄、強制 branch 削除は、この skill の自動手順に含めません。
