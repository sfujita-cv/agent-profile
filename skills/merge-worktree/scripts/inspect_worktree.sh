#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  inspect_worktree.sh <worktree-path> [main-path]

Prints branch/status information for a git worktree and the main checkout.
USAGE
}

if [[ $# -lt 1 || $# -gt 2 ]]; then
  usage
  exit 2
fi

worktree_path=$1
main_path=${2:-.}

if [[ ! -d "$worktree_path" ]]; then
  echo "error: worktree path does not exist: $worktree_path" >&2
  exit 1
fi

if ! git -C "$worktree_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: not a git worktree: $worktree_path" >&2
  exit 1
fi

if ! git -C "$main_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: not a git checkout: $main_path" >&2
  exit 1
fi

worktree_common=$(git -C "$worktree_path" rev-parse --path-format=absolute --git-common-dir)
main_common=$(git -C "$main_path" rev-parse --path-format=absolute --git-common-dir)

echo "== Repository =="
echo "worktree: $worktree_path"
echo "main:     $main_path"
echo "same repository: $([[ "$worktree_common" == "$main_common" ]] && echo yes || echo no)"
echo

echo "== Worktree branch =="
git -C "$worktree_path" branch --show-current
echo

echo "== Worktree status =="
git -C "$worktree_path" status --short
echo

echo "== Worktree changed files =="
git -C "$worktree_path" diff --name-status
git -C "$worktree_path" ls-files --others --exclude-standard | sed 's/^/??\t/'
echo

echo "== Main branch =="
git -C "$main_path" branch --show-current
echo

echo "== Main status =="
git -C "$main_path" status --short
echo

echo "== Worktree commits not in main =="
branch=$(git -C "$worktree_path" branch --show-current)
main_branch=$(git -C "$main_path" branch --show-current)
if [[ -n "$branch" && -n "$main_branch" ]]; then
  git -C "$main_path" log --oneline "${main_branch}..${branch}" || true
fi
