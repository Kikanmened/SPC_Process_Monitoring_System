"""Reading the code revision that produced a result."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spc_platform.infrastructure.vcs import (
    DIRTY_SUFFIX,
    UNKNOWN_REVISION,
    current_code_revision,
)


def git(*arguments: str, cwd: Path) -> None:
    """Run a git command in a scratch repository, failing loudly."""
    subprocess.run(  # noqa: S603
        ["git", *arguments],  # noqa: S607
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    """Return a scratch git repository holding one commit."""
    git("init", "--quiet", cwd=tmp_path)
    git("config", "user.email", "test@example.invalid", cwd=tmp_path)
    git("config", "user.name", "Test", cwd=tmp_path)
    (tmp_path / "file.txt").write_text("one\n", encoding="utf-8")
    git("add", "file.txt", cwd=tmp_path)
    git("commit", "--quiet", "-m", "initial", cwd=tmp_path)
    return tmp_path


def test_a_clean_tree_reports_its_commit(repository: Path) -> None:
    revision = current_code_revision(repository)

    assert len(revision) == 12
    assert not revision.endswith(DIRTY_SUFFIX)


def test_a_modified_tree_is_marked_dirty(repository: Path) -> None:
    """An uncommitted change is admitted rather than hidden.

    A result produced from uncommitted code is not reproducible from any commit,
    and naming the bare hash would point an audit at the wrong code.
    """
    (repository / "file.txt").write_text("two\n", encoding="utf-8")

    assert current_code_revision(repository).endswith(DIRTY_SUFFIX)


def test_an_untracked_file_also_marks_the_tree_dirty(repository: Path) -> None:
    (repository / "new.txt").write_text("new\n", encoding="utf-8")

    assert current_code_revision(repository).endswith(DIRTY_SUFFIX)


def test_outside_a_checkout_the_revision_is_unknown(tmp_path: Path) -> None:
    """Honest rather than absent: 'unknown' is a value an audit can act on."""
    assert current_code_revision(tmp_path) == UNKNOWN_REVISION


def test_a_git_that_cannot_be_run_yields_unknown(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Absent, broken, and failing git are one outcome to a caller."""

    def explode(*_args: object, **_kwargs: object) -> None:
        raise OSError("git is not installed")

    monkeypatch.setattr(subprocess, "run", explode)

    assert current_code_revision(repository) == UNKNOWN_REVISION


def test_a_hanging_git_yields_unknown(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Provenance capture must not be able to stall a generation run."""

    def time_out(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="git", timeout=10)

    monkeypatch.setattr(subprocess, "run", time_out)

    assert current_code_revision(repository) == UNKNOWN_REVISION
