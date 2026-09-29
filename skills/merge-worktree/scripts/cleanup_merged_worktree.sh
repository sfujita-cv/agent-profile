#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE' >&2
Usage:
  cleanup_merged_worktree.sh <worktree-path> [main-path]

Removes a clean merged worktree and deletes its branch with `git branch -d`.
The worktree branch must already be an ancestor of the main checkout branch.
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
worktree_top=$(git -C "$worktree_path" rev-parse --show-toplevel)

if [[ -z "$branch" ]]; then
  echo "error: detached HEAD worktrees are not supported by this script" >&2
  exit 1
fi

if [[ -z "$main_branch" ]]; then
  echo "error: main checkout is detached" >&2
  exit 1
fi

if [[ "$branch" == "$main_branch" ]]; then
  echo "error: refusing to remove the main branch worktree: $branch" >&2
  exit 1
fi

if [[ -n "$(git -C "$worktree_path" status --porcelain)" ]]; then
  echo "error: worktree has uncommitted changes; refusing cleanup" >&2
  git -C "$worktree_path" status --short >&2
  exit 1
fi

if [[ -n "$(git -C "$main_path" status --porcelain)" ]]; then
  echo "error: main checkout has uncommitted changes; refusing cleanup" >&2
  git -C "$main_path" status --short >&2
  exit 1
fi

if ! git -C "$main_path" merge-base --is-ancestor "$branch" "$main_branch"; then
  echo "error: branch '$branch' is not fully merged into '$main_branch'" >&2
  exit 1
fi

echo "Removing worktree: $worktree_top"
# submodule を含む worktree は --force なしでは remove できない (git の制約)。
# 未 commit 変更が無いことは上で確認済みなので、ここでの --force は破棄を意味しない。
git -C "$main_path" worktree remove --force "$worktree_top"

echo "Deleting merged branch: $branch"
git -C "$main_path" branch -d "$branch"
