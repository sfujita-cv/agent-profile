#!/usr/bin/env bash
###############################################################################
# ai-pr-draft.sh
#   直近の commit と diff を Claude に渡して、日本語の Draft PR を gh CLI で作る。
#   - protected branch (main, develop, staging 等) では中断する。
#   - 各 step をログに出す。DEBUG=1 で shell trace を有効化。
#   - 特定のリポジトリに依存しない。
#
#   commit log と diff は **stdin** で渡す。argv に載せると大きな diff で
#   execve(2) の ARG_MAX を超えて "Argument list too long" になるため。
###############################################################################

# ---- Runtime options ---------------------------------------------------------
DEBUG=${DEBUG:-0}            # DEBUG=1 ./script … で set -x
TRACE_COLOR="\033[1;34m"   # Blue
RESET_COLOR="\033[0m"

# diff を stdin に載せる上限。ARG_MAX の問題は無くなるが、モデルの context は有限。
DIFF_MAX_LINES=${DIFF_MAX_LINES:-4000}
DIFF_MAX_BYTES=${DIFF_MAX_BYTES:-400000}

set -euo pipefail
[[ $DEBUG -eq 1 ]] && set -x

# ---- Helper ------------------------------------------------------------------
log() { echo -e "${TRACE_COLOR}[$(date +%H:%M:%S)] $*${RESET_COLOR}"; }
trap 'log "❌ Error at line ${LINENO}: \"${BASH_COMMAND}\""' ERR

WORK_DIR=$(mktemp -d)
cleanup() { rm -rf "$WORK_DIR"; }
trap cleanup EXIT

# ---- Tool checks -------------------------------------------------------------
log "Step 0: 必要なツールを確認…"
for cmd in gh claude jq python3; do
  command -v "$cmd" >/dev/null || { echo "❌ $cmd not found" >&2; exit 1; }
  log "  ✓ $cmd found"
done

# ---- Variables ---------------------------------------------------------------
log "Step 1: リポジトリの情報を収集…"
REPO=$(gh repo view --json nameWithOwner --jq .nameWithOwner)

# base branch を自動判定
DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)
if [[ -z "$DEFAULT_BRANCH" ]]; then
  DEFAULT_BRANCH="main"
  log "  ⚠️  default branch を判定できないため 'main' を使う"
fi

BRANCH=$(git rev-parse --abbrev-ref HEAD)
log "  repo:            $REPO"
log "  base branch:     $DEFAULT_BRANCH"
log "  current branch:  $BRANCH"

# ---- Protected branch guard --------------------------------------------------
if [[ "$BRANCH" =~ ^(main|master|develop|staging|production)$ ]]; then
  echo "❌ '$BRANCH' は protected branch です。直接 PR は作れません。別 branch で作業してください。" >&2
  exit 1
fi

# ---- Collect commits & diff --------------------------------------------------
log "Step 2: commit と diff を収集…"
COMMITS=$(git log "$DEFAULT_BRANCH..$BRANCH" --pretty=format:"- %s (%an, %ad)" --date=short)
DIFFSTAT=$(git diff "$DEFAULT_BRANCH...$BRANCH" --stat || true)
DIFF_RAW=$( (git diff "$DEFAULT_BRANCH...$BRANCH" || true) | head -n "$DIFF_MAX_LINES" | head -c "$DIFF_MAX_BYTES" )
log "  commits: $(printf '%s\n' "$COMMITS" | wc -l) 件"
log "  diff: $(printf '%s' "$DIFF_RAW" | wc -l) 行 / $(printf '%s' "$DIFF_RAW" | wc -c) bytes (上限で truncate)"

# ---- Pull-request template ---------------------------------------------------
TPL_CONTENT=""
for tpl in .github/PULL_REQUEST_TEMPLATE_JA.md .github/PULL_REQUEST_TEMPLATE.md; do
  if [[ -f "$tpl" ]]; then
    log "  template found: $tpl"
    TPL_CONTENT=$(cat "$tpl")
    break
  fi
done
if [[ -z "$TPL_CONTENT" ]]; then
  log "  template が無いので既定の日本語構成を使う"
  TPL_CONTENT="## 概要

この変更の目的と背景を簡潔に書く。

## 変更点

この PR で何を変えたかを列挙する。

## 検証

実行した検証と結果を書く。実行していない検証は「未実行」と明記する。

## チェックリスト

- [ ] 機能要件を満たしている
- [ ] テストを追加・更新した
- [ ] ドキュメントを更新した (必要な場合)"
fi

# ---- Build prompt ------------------------------------------------------------
# instruction は argv、可変長の context は stdin。
log "Step 3: Claude に PR title / body を生成させる…"

CONTEXT_FILE="$WORK_DIR/context.txt"
{
  echo "Repository: $REPO"
  echo "Branch: $BRANCH -> $DEFAULT_BRANCH"
  echo
  echo "## Recent commits"
  echo "$COMMITS"
  echo
  echo "## Diff stat"
  echo "$DIFFSTAT"
  echo
  echo "## Git diff (truncated)"
  echo "$DIFF_RAW"
  echo
  echo "## PR テンプレート"
  echo "$TPL_CONTENT"
} > "$CONTEXT_FILE"
log "  context: $(wc -c < "$CONTEXT_FILE") bytes (stdin 経由で渡す)"

INSTRUCTIONS='あなたはシニアエンジニアとして pull request の下書きを作ります。
コマンドは実行せず、stdin で渡された情報だけを読んでください。

stdin には commit log、diff stat、diff、PR テンプレートが入っています。これらを読んで
PR の title と body を生成してください。

**言語**: title の説明部分と body は必ず日本語で書きます。
Conventional Commits の type 接頭辞 (feat: / fix: / docs: / refactor: / test: / chore: / perf: / ci:)
と、識別子・API 名・path・設定キー・ログの key は英語のままにします。

**書き方**:
1. body は stdin の PR テンプレートの節構成に従う
2. チェックボックスは変更内容に照らして妥当なものだけ checked にする
3. 節と節の間には空行を入れる
4. diff は truncate されている可能性がある。読み取れた範囲だけを根拠に書き、憶測で検証結果を書かない
5. 検証について書けることが無ければ「未実行」と明記する

**出力形式**: 次の JSON だけを ```json コードフェンスで囲んで返す。他の文章は付けない。

```json
{"title": "feat: 機能の説明", "body": "## 概要\n\n変更の説明…"}
```

- 改行は \n としてエスケープする
- ダブルクォートは \" としてエスケープする
- JSON 全体を 1 行で出力する'

# ---- Query Claude with retry logic -------------------------------------------
log "  Claude に問い合わせ中…"
CLAUDE_JSON=""
MAX_RETRIES=3
RETRY_COUNT=0

while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  log "  Attempt $RETRY_COUNT/$MAX_RETRIES…"

  # stderr は分けて捨てる。stdout に混ぜると --output-format json の応答が
  # 警告行で汚れて parse できなくなる。
  if CLAUDE_JSON=$(claude -p "$INSTRUCTIONS" --output-format json \
                     < "$CONTEXT_FILE" 2>"$WORK_DIR/claude_err.txt"); then
    log "  ✓ Claude が応答した"
    break
  else
    log "  ⚠️  Claude への問い合わせが失敗 (attempt $RETRY_COUNT/$MAX_RETRIES)"
    if [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; then
      SLEEP_TIME=$((2 ** (RETRY_COUNT - 1)))  # 1, 2, 4 秒
      log "  ${SLEEP_TIME} 秒後に再試行…"
      sleep $SLEEP_TIME
    else
      echo "❌ Claude への問い合わせが $MAX_RETRIES 回とも失敗:" >&2
      cat "$WORK_DIR/claude_err.txt" >&2
      echo "$CLAUDE_JSON" >&2
      exit 1
    fi
  fi
done

printf '%s' "$CLAUDE_JSON" > "$WORK_DIR/claude_raw.json"
if [[ $DEBUG -eq 1 ]]; then
  echo "DEBUG: Claude raw output (first 1000 chars):" >&2
  head -c 1000 "$WORK_DIR/claude_raw.json" >&2
  echo "…" >&2
fi

# ---- Extract title / body ----------------------------------------------------
# Claude CLI の応答 (--output-format json) から .result を取り、その中の JSON を取り出す。
# title / body を別ファイルに書き出すので、改行や引用符を shell で壊さない。
log "Step 4: title / body を抽出…"
TITLE_FILE="$WORK_DIR/title.txt"
BODY_FILE="$WORK_DIR/body.md"

python3 - "$WORK_DIR/claude_raw.json" "$TITLE_FILE" "$BODY_FILE" <<'PY'
import json
import pathlib
import re
import sys

raw_path, title_path, body_path = (pathlib.Path(p) for p in sys.argv[1:4])
raw = raw_path.read_text(encoding="utf-8", errors="replace")

# 1. Claude CLI の外側 JSON をほどく。形式は version によって
#    単一 object (.result) と event 配列のどちらもありうる。
text = raw
try:
    outer = json.loads(raw)
except json.JSONDecodeError:
    pass
else:
    if isinstance(outer, dict) and isinstance(outer.get("result"), str):
        text = outer["result"]
    elif isinstance(outer, list):
        for event in reversed(outer):
            if isinstance(event, dict) and event.get("type") == "assistant":
                content = event.get("message", {}).get("content", [])
                if content and isinstance(content[0], dict):
                    text = content[0].get("text", text)
                break

# 2. code fence があれば中身を優先する。
fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.DOTALL)
candidates = [fence.group(1)] if fence else []
candidates.append(text)

# 3. title / body を持つ JSON object を探す。前後に説明文が付いていても拾えるよう、
#    最初の '{' から順に raw_decode を試す。
decoder = json.JSONDecoder()
for candidate in candidates:
    for start in (m.start() for m in re.finditer(r"\{", candidate)):
        try:
            obj, _ = decoder.raw_decode(candidate[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("title") and obj.get("body"):
            title_path.write_text(str(obj["title"]).strip() + "\n", encoding="utf-8")
            body_path.write_text(str(obj["body"]).rstrip() + "\n", encoding="utf-8")
            sys.exit(0)

print("could not find a JSON object with both 'title' and 'body'", file=sys.stderr)
print("--- response (first 2000 chars) ---", file=sys.stderr)
print(text[:2000], file=sys.stderr)
sys.exit(1)
PY

TITLE=$(head -n 1 "$TITLE_FILE")
[[ -n "$TITLE" ]] || { echo "❌ title が空です" >&2; exit 1; }
[[ -s "$BODY_FILE" ]] || { echo "❌ body が空です" >&2; exit 1; }

# attribution trailer (CLAUDE.md の規約)
if ! grep -qF "Generated with [Claude Code]" "$BODY_FILE"; then
  printf '\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n' >> "$BODY_FILE"
fi

log "  Title: $TITLE"
log "  Body:  $(wc -c < "$BODY_FILE") bytes"

# ---- Push branch to remote ---------------------------------------------------
log "Step 5: branch を remote へ push…"
if git push -u origin "$BRANCH"; then
  log "  ✓ push 完了"
else
  echo "❌ branch の push に失敗しました。権限を確認してください。" >&2
  exit 1
fi

# ---- Create Draft PR ---------------------------------------------------------
log "Step 6: draft PR を作成…"
log "    Title: $TITLE"
log "    Base:  $DEFAULT_BRANCH"
log "    Head:  $BRANCH"

PR_CREATE_EXIT_CODE=0
PR_CREATE_OUTPUT=$(gh pr create \
  --title "$TITLE" \
  --body-file "$BODY_FILE" \
  --base "$DEFAULT_BRANCH" \
  --head "$BRANCH" \
  --draft \
  2>&1) || PR_CREATE_EXIT_CODE=$?

if [[ $PR_CREATE_EXIT_CODE -eq 0 ]]; then
  log "✅ Draft PR を作成しました"
  log "   URL: $PR_CREATE_OUTPUT"
else
  echo "❌ PR の作成に失敗しました (exit code: $PR_CREATE_EXIT_CODE)" >&2
  echo "$PR_CREATE_OUTPUT" >&2
  echo "" >&2
  echo "Debug information:" >&2
  echo "  Repository:  $REPO" >&2
  echo "  Base branch: $DEFAULT_BRANCH" >&2
  echo "  Head branch: $BRANCH" >&2
  echo "  Title:       $TITLE" >&2
  echo "  Body (先頭 10 行):" >&2
  head -10 "$BODY_FILE" >&2
  echo "" >&2
  gh auth status >&2 || echo "gh auth status に失敗" >&2
  git ls-remote --heads origin "$BRANCH" >&2 || echo "head branch が remote に無い" >&2
  git ls-remote --heads origin "$DEFAULT_BRANCH" >&2 || echo "base branch が remote に無い" >&2
  exit 1
fi

log "🎉 完了"
