"""Enforce Conventional Commits on the message being written.

CODING_STANDARDS.md §11 marks this [ENFORCED]. The reason it is worth
enforcing here rather than reviewing later is the ``stat`` marker: a change to
statistical behaviour retroactively alters the meaning of every historical
number, and those commits have to be trivially findable in history years after
the fact (QUALITY_ASSURANCE_PLAN.md §6).

The documents write that marker as ``stat:``, so it is accepted as a type; it
is also accepted as a scope, because ``fix(stat): ...`` expresses the same
thing and reviewers write both.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TYPES = (
    "build",
    "chore",
    "ci",
    "docs",
    "feat",
    "fix",
    "perf",
    "refactor",
    "revert",
    "stat",
    "style",
    "test",
)

SUBJECT = re.compile(
    r"^(?P<type>" + "|".join(TYPES) + r")"
    r"(?:\((?P<scope>[a-z0-9][a-z0-9._/-]*)\))?"
    r"(?P<breaking>!)?"
    r": (?P<summary>\S.*)$"
)

# Messages git generates or that a rebase workflow produces are not authored
# subjects and are left alone.
EXEMPT_PREFIXES = ("Merge ", "Revert ", "fixup! ", "squash! ", "amend! ")

MAX_SUBJECT_LENGTH = 72

# The hook is invoked as `check_commit_message.py <path>`.
EXPECTED_ARGUMENT_COUNT = 2


def problems_with(subject: str) -> list[str]:
    """Return every rule the subject line breaks."""
    found: list[str] = []
    match = SUBJECT.match(subject)
    if match is None:
        found.append(f"does not match 'type(optional-scope): summary'. Types: {', '.join(TYPES)}")
        return found

    if len(subject) > MAX_SUBJECT_LENGTH:
        found.append(f"is {len(subject)} characters; the limit is {MAX_SUBJECT_LENGTH}")

    summary = match.group("summary")
    if summary.endswith("."):
        found.append("ends with a full stop")
    if summary[0].isupper() and not summary.split()[0].isupper():
        found.append("starts with a capital letter; the summary is lower case")

    return found


def main() -> int:
    if len(sys.argv) != EXPECTED_ARGUMENT_COUNT:
        print("usage: check_commit_message.py <path-to-commit-message>")
        return 2

    lines = Path(sys.argv[1]).read_text(encoding="utf-8").splitlines()
    body = [line for line in lines if not line.startswith("#")]
    if not body or not body[0].strip():
        print("Commit message is empty.")
        return 1

    subject = body[0].rstrip()
    if subject.startswith(EXEMPT_PREFIXES):
        return 0

    found = problems_with(subject)
    if not found:
        return 0

    print(f"Commit subject: {subject}")
    for problem in found:
        print(f"  - {problem}")
    print()
    print("Examples:")
    print("  feat(domain): add ControlLimit value object")
    print("  stat: correct d2 constant for subgroup size 2")
    print("  fix(pipelines)!: reject rows with a naive timestamp")
    return 1


if __name__ == "__main__":
    sys.exit(main())
