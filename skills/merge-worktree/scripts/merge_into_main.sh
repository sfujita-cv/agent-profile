#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  merge_into_main.sh <worktree-path> [main-path]

Merges the worktree branch into the current main checkout.
The main checkout must be clean. This script does not delete branches or worktrees.
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
if [[ "$worktree_common" != "$main_common" ]]; then
  echo "error: worktree and main checkout are not from the same repository" >&2
  exit 1
fi

branch=$(git -C "$worktree_path" branch --show-current)
main_branch=$(git -C "$main_path" branch --show-current)

if [[ -z "$branch" ]]; then
  echo "error: detached HEAD worktrees are not supported by this script" >&2
  exit 1
fi

if [[ -z "$main_branch" ]]; then
  echo "error: main checkout is detached" >&2
  exit 1
fi

if [[ "$branch" == "$main_branch" ]]; then
  echo "error: worktree branch and main branch are the same: $branch" >&2
  exit 1
fi

if [[ -n "$(git -C "$main_path" status --porcelain)" ]]; then
  echo "error: main checkout has uncommitted changes; commit or move them before merging" >&2
  git -C "$main_path" status --short >&2
  exit 1
fi

if [[ -n "$(git -C "$worktree_path" status --porcelain)" ]]; then
  echo "error: worktree has uncommitted changes; commit logical groups first" >&2
  git -C "$worktree_path" status --short >&2
  exit 1
fi

echo "Merging branch '$branch' into '$main_branch'"
git -C "$main_path" merge --no-ff "$branch"
