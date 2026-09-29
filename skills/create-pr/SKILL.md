---
name: create-pr
description: ローカルのgitプロジェクトで直近のコミット内容を元に、日本語のドラフトPRを自動生成するスキル。「PRを作って」「pull requestを作成して」「PRのドラフトを出して」など、PR作成に関する依頼があれば必ずこのスキルを使うこと。デバッグモードでの実行にも対応している。
---

# PR Draft 作成スキル

直近の git コミットと diff を解析し、Claude が**日本語**のドラフト PR を自動生成するスキル。

---

## 事前確認

push / PR 作成は worktree の成果が外に出る契機です。`docs/<worktree-name>/YYYY-MM-DD-hhmm.md` の記録が未作成なら、
先に `~/.claude/skills/worktree-retrospective/SKILL.md` の手順を通してから PR を作ります。

## 言語

`CLAUDE.md` の「回答と説明文書の言語方針」に従い、**PR の title と body は日本語**で書きます。

英語のまま残すのは次だけです。

- Conventional Commits の type 接頭辞 (`feat:` / `fix:` / `docs:` / `refactor:` / `test:` / `chore:` / `perf:` / `ci:`)
- 識別子、API 名、file path、設定キー、ログの key、外部ライブラリ由来の用語

## 実行手順

### 通常実行

以下のスクリプトを実行して、ドラフト PR を作成する：

```bash
bash ~/.claude/skills/create-pr/scripts/ai-pr-draft.sh
```

### デバッグモードで実行

問題が発生した場合や詳細ログを確認したい場合は、`DEBUG=1` を付けて実行する：

```bash
DEBUG=1 bash ~/.claude/skills/create-pr/scripts/ai-pr-draft.sh
```

### 生成結果に手を入れる場合

スクリプトが渡す diff は上限で truncate されるため、**検証の実行結果や、diff からは読み取れない
経緯はスクリプトの出力には入りません**。それらが重要な PR では、スクリプトで下書きを作ったあとに
`gh pr edit <番号> --body-file <file>` で加筆します。

## 動作の概要

- スクリプト（`ai-pr-draft.sh`）が PR 作成・AI 連携・git 操作のすべてのロジックを担う
- commit log と diff は **stdin** で Claude に渡す。argv に載せると大きな diff で
  `Argument list too long` (`MAX_ARG_STRLEN` = 128 KiB) になるため
- diff は `DIFF_MAX_LINES` (既定 4000 行) と `DIFF_MAX_BYTES` (既定 400000 bytes) で truncate する
- PR テンプレートは `.github/PULL_REQUEST_TEMPLATE_JA.md` → `.github/PULL_REQUEST_TEMPLATE.md` の順に探し、
  どちらも無ければ組み込みの日本語構成（概要 / 変更点 / 検証 / チェックリスト）を使う
- body 末尾に `🤖 Generated with [Claude Code](...)` を付ける（既に含まれていれば付けない）

## ディレクトリ構成

```
project_root/
└── .claude/
    └── skills/
        └── create-pr/
            ├── SKILL.md          # このファイル
            └── scripts/
                └── ai-pr-draft.sh
```

---

## キーワード

PR, pull request, ドラフト, draft, git, コミット, commit, GitHub, レビュー
