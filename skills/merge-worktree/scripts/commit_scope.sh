#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  commit_scope.sh <worktree-path> <commit-message> -- <pathspec>...

Stages the given pathspecs inside the worktree and creates one commit.
Use this once per logical change group.
USAGE
}

if [[ $# -lt 4 ]]; then
  usage
  exit 2
fi

worktree_path=$1
message=$2
shift 2

if [[ "${1:-}" != "--" ]]; then
  echo "error: expected -- before pathspecs" >&2
  usage
  exit 2
fi
shift

if [[ $# -lt 1 ]]; then
  echo "error: at least one pathspec is required" >&2
  exit 2
fi

if [[ ! -d "$worktree_path" ]]; then
  echo "error: worktree path does not exist: $worktree_path" >&2
  exit 1
fi

if ! git -C "$worktree_path" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: not a git worktree: $worktree_path" >&2
  exit 1
fi

branch=$(git -C "$worktree_path" branch --show-current)
if [[ -z "$branch" ]]; then
  echo "error: detached HEAD worktrees are not supported by this script" >&2
  exit 1
fi

git -C "$worktree_path" add -- "$@"

if git -C "$worktree_path" diff --cached --quiet; then
  echo "error: no staged changes for the provided pathspecs" >&2
  exit 1
fi

echo "== Staged changes =="
git -C "$worktree_path" diff --cached --stat
echo

git -C "$worktree_path" commit -m "$message"
