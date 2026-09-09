"""Remove only an unchanged local branch/worktree belonging to a merged PR."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(root: Path, *command: str) -> str:
    return subprocess.run(
        command, cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def cleanup(root: Path, number: str) -> None:
    if run(root, "git", "branch", "--show-current") != "main":
        raise ValueError("run cleanup from the main checkout, not the topic worktree")
    if run(root, "git", "status", "--porcelain"):
        raise ValueError("main checkout must be clean, including untracked files")
    pr = json.loads(
        run(
            root,
            "gh",
            "pr",
            "view",
            number,
            "--json",
            "state,baseRefName,headRefName,headRefOid,mergeCommit,isCrossRepository",
        )
    )
    if pr["state"] != "MERGED" or pr["baseRefName"] != "main" or pr["isCrossRepository"]:
        raise ValueError("cleanup requires a merged, same-repository PR targeting main")
    branch = pr["headRefName"]
    if branch == "main":
        raise ValueError("cannot delete main")
    run(root, "git", "fetch", "origin", "main")
    run(root, "git", "merge-base", "--is-ancestor", pr["mergeCommit"]["oid"], "origin/main")
    branches = run(root, "git", "for-each-ref", "--format=%(refname)", "refs/heads").splitlines()
    if f"refs/heads/{branch}" not in branches:
        print(f"Local branch {branch} is already absent.")
        return
    tip = run(root, "git", "rev-parse", f"refs/heads/{branch}")
    if tip != pr["headRefOid"]:
        raise ValueError("local branch has changed since the merged PR; retain it for review")
    run(root, "git", "merge", "--ff-only", "origin/main")
    worktree = None
    for field in run(root, "git", "worktree", "list", "--porcelain", "-z").split("\0"):
        if field.startswith("worktree "):
            worktree = Path(field.removeprefix("worktree "))
        if field == f"branch refs/heads/{branch}" and worktree is not None:
            if run(worktree, "git", "status", "--porcelain"):
                raise ValueError(f"topic worktree has changes: {worktree}")
            # No --force: Git also refuses locked or otherwise unsafe worktree removal.
            run(root, "git", "worktree", "remove", str(worktree))
    # Squash merges do not preserve ancestry. The exact PR head comparison above is required.
    run(root, "git", "branch", "-D", "--", branch)
    print(f"Removed merged local branch {branch} and its clean worktree, if present.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr", type=int)
    args = parser.parse_args()
    try:
        cleanup(ROOT, str(args.pr))
    except (ValueError, subprocess.CalledProcessError) as exc:
        detail = exc.stderr if isinstance(exc, subprocess.CalledProcessError) else str(exc)
        parser.exit(1, f"Cleanup stopped: {detail or exc}\n")
