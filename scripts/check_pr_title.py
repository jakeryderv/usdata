"""Validate the title that GitHub will use for a squash commit."""

import os
import re
import sys

TITLE = re.compile(
    r"(?:build|chore|ci|docs|feat|fix|perf|refactor|revert|style|test)"
    r"(?:\([^()\r\n]+\))?!?: [^\s][^\r\n]*"
)


def valid_title(title: str) -> bool:
    return TITLE.fullmatch(title) is not None


if __name__ == "__main__":
    if not valid_title(os.environ.get("PR_TITLE", "")):
        sys.exit("Use a Conventional Commit PR title, for example: feat: add a dataset")
    print("PR title is a Conventional Commit")
