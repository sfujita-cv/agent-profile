---
name: phased-plan
description: >
  Create a phased implementation plan in plans/ for cross-model review.
  Use before starting non-trivial features. The output file is designed
  to be reviewed by Codex CLI in Terminal 2 (Step 2 of the 4-step cycle).
  "plan", "計画を作って", "設計して" などで呼び出す。
user-invocable: true
argument-hint: "[feature name or description]"
---

# Plan: フェーズ分割された実装計画の作成

4 ステップ cross-model サイクルの Step 1。
Claude Code が計画を `plans/{YYYY-MM-DD}_{feature-name}.md` に書き出し、次のステップで Codex CLI (Terminal 2) がレビューできる形にする。

## Context: $ARGUMENTS

## ワークフロー

### Step 1: 機能の意図を把握する

- **引数あり**: 引数をそのまま機能名・説明として使う
- **引数なし**: 直近の会話から推測する。推測できなければユーザーに確認する

feature-name はケバブケース (例: `add-user-authentication`, `refactor-cache-layer`)。

### Step 2: コードベースを探索する

計画に必要なコンテキストを収集する:

- プロジェクトの CLAUDE.md / README.md (設計方針、制約)
- 関連するソースコード (`src/` 配下)
- 既存のテスト (`tests/` 配下)
- 依存関係 (`pixi.toml` or `pyproject.toml`)
- ディレクトリ構成と主要なインターフェース

### Step 3: 計画ファイルを生成する

`plans/{YYYY-MM-DD}_{feature-name}.md` に以下の構造で書き出す:

```markdown
# Plan: {feature-name}

## Context

{なぜこの変更が必要か、何を達成するか}

## Relevant Code

- `src/xxx.py` — {このファイルが関連する理由}
- `tests/test_xxx.py` — {既存テストの状況}

## Phases

### Phase 1: {タイトル}

{変更内容の説明。どのファイルを作成/変更するか。}

#### Test Gate

- [ ] {このフェーズ完了の判定基準}
- [ ] `pixi run test` が通る

<!-- Codex Finding -->

### Phase 2: {タイトル}

...

#### Test Gate

- [ ] ...

<!-- Codex Finding -->

## Summary

- **期待される成果**: {最終的にどうなるか}
- **リスク**: {注意すべき点}
- **依存関係**: {新しいパッケージが必要か}
```

### Step 4: ユーザーに次のステップを案内する

計画ファイルの生成後、以下を伝える:

```
plans/{YYYY-MM-DD}_{feature-name}.md を生成しました。

次のステップ:
  Terminal 2 (Codex CLI) で以下を実行してください:
  > plans/{feature-name}.md の計画をレビューして。コードベースと照合し、見落としや問題があれば "Codex Finding" として追記して。元のフェーズは書き換えないで。
```

## ルール

- 1 フェーズは 1 つの論理的変更単位。大きすぎず小さすぎず
- 各フェーズに必ず Test Gate を含める (検証可能な判定基準)
- `<!-- Codex Finding -->` コメントは空のまま残す (Codex CLI が記入する)
- 既存コードの変更が必要な場合、影響範囲を Phase ごとに明記する
- 新しい依存関係が必要な場合、`pixi add` コマンドを Phase に含める
- 計画は簡潔に。ソースコード全体を貼らない (要約とファイルパスで十分)
