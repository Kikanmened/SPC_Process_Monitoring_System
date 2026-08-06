"""Read the code revision from the version control system.

Every result the platform emits carries a ``code_revision`` (FR-RP02), and
discovering it means running ``git``. That is I/O against an external tool, so
it belongs here rather than in ``common/`` — nothing above this layer shells
out, and nothing below it knows a repository exists.
"""

from __future__ import annotations

# Running git is the only way to ask git anything; see _git for why that is safe.
import subprocess  # nosec B404
from pathlib import Path

from spc_platform.domain.ids import CodeRevision

UNKNOWN_REVISION = CodeRevision("unknown")
"""Recorded when the revision cannot be read at all — no checkout, or no git."""

DIRTY_SUFFIX = "-dirty"
"""Marks a revision that does not describe the code that actually ran."""

_HASH_LENGTH = 12
_GIT_TIMEOUT_SECONDS = 10


def current_code_revision(repository: Path | None = None) -> CodeRevision:
    """Return the short commit hash, suffixed with ``-dirty`` for a modified tree.

    The suffix is not cosmetic. A result produced from uncommitted code is not
    reproducible from any commit, and recording the bare hash would name a
    revision that produces something else — an audit trail that points at the
    wrong code is worse than one that admits it does not know.

    Parameters
    ----------
    repository
        Directory to read the revision from. Defaults to the working directory.

    Returns
    -------
    CodeRevision
        The revision, or ``UNKNOWN_REVISION`` outside a git checkout.
    """
    head = _git(("rev-parse", f"--short={_HASH_LENGTH}", "HEAD"), repository)
    if head is None:
        return UNKNOWN_REVISION
    modified = _git(("status", "--porcelain"), repository)
    if modified:
        return CodeRevision(f"{head}{DIRTY_SUFFIX}")
    return CodeRevision(head)


def _git(arguments: tuple[str, ...], repository: Path | None) -> str | None:
    """Run one git command, returning its stripped output or None on any failure.

    Absent, broken, and non-zero-exit git are the same outcome to a caller: the
    revision is unknown. Distinguishing them would offer a choice nobody can act
    on.
    """
    # The argv is fixed and no shell is involved, so nothing a caller passes can
    # become a command. git is resolved from PATH on purpose: an absolute path
    # would be wrong on every machine but the one it was written on, and a PATH
    # an attacker can rewrite is a machine already lost.
    try:
        completed = subprocess.run(  # noqa: S603  # nosec B603 B607
            ["git", *arguments],  # noqa: S607
            cwd=repository,
            capture_output=True,
            text=True,
            check=False,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()
