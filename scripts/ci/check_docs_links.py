"""Validate every internal Markdown link and anchor in the repository.

QUALITY_ASSURANCE_PLAN.md §8 makes a broken cross-reference a defect rather
than an annoyance: the documentation set is the project's source of truth, and
a link that silently stops resolving is how a source of truth quietly stops
being one.

External links are not fetched. This check runs in an air-gapped environment
and must not depend on a network, so it verifies only what the repository can
prove about itself.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        ".tools",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        "htmlcov",
    }
)

SKIP_SCHEMES = ("http://", "https://", "mailto:", "tel:", "ftp://")

INLINE_LINK = re.compile(r"!?\[(?:[^\]]*)\]\(\s*<?(?P<target>[^)<>\s]+)>?(?:\s+\"[^\"]*\")?\s*\)")
HEADING = re.compile(r"^(?P<hashes>#{1,6})\s+(?P<title>.+?)\s*#*\s*$")
EXPLICIT_ANCHOR = re.compile(r"<a\s+(?:id|name)\s*=\s*[\"'](?P<anchor>[^\"']+)[\"']")
FENCE = re.compile(r"^\s*(?P<ticks>```+|~~~+)")


def slugify(title: str) -> str:
    """Convert a heading to the fragment identifier GitHub generates for it."""
    text = re.sub(r"<[^>]+>", "", title)
    text = re.sub(r"[`*]", "", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    return re.sub(r"\s+", "-", text)


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.md")
        if not SKIP_DIRECTORIES.intersection(path.relative_to(REPO_ROOT).parts)
    )


def anchors_of(path: Path) -> set[str]:
    """Return every fragment identifier the given Markdown file defines."""
    anchors: set[str] = set()
    seen: dict[str, int] = {}
    for line, in_code in iter_lines(path):
        anchors.update(match.group("anchor") for match in EXPLICIT_ANCHOR.finditer(line))
        if in_code:
            continue
        heading = HEADING.match(line)
        if heading is None:
            continue
        slug = slugify(heading.group("title"))
        if not slug:
            continue
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def iter_lines(path: Path) -> list[tuple[str, bool]]:
    """Return each line paired with whether it sits inside a fenced code block."""
    result: list[tuple[str, bool]] = []
    fence: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = FENCE.match(line)
        if match is not None:
            ticks = match.group("ticks")
            if fence is None:
                fence = ticks
                result.append((line, True))
                continue
            if ticks.startswith(fence[0]) and len(ticks) >= len(fence):
                fence = None
                result.append((line, True))
                continue
        result.append((line, fence is not None))
    return result


def check_file(path: Path, anchor_cache: dict[Path, set[str]]) -> list[str]:
    """Return one message per broken link found in the given file."""
    problems: list[str] = []
    relative = path.relative_to(REPO_ROOT)
    for number, (line, in_code) in enumerate(iter_lines(path), start=1):
        if in_code:
            continue
        for match in INLINE_LINK.finditer(line):
            target = match.group("target")
            if target.startswith(SKIP_SCHEMES):
                continue
            location, _, fragment = target.partition("#")
            if location:
                resolved = (path.parent / location).resolve()
                if not resolved.exists():
                    problems.append(f"{relative}:{number}: target does not exist: {target}")
                    continue
            else:
                resolved = path
            if not fragment or resolved.is_dir():
                continue
            if resolved.suffix.lower() != ".md":
                continue
            if resolved not in anchor_cache:
                anchor_cache[resolved] = anchors_of(resolved)
            if fragment not in anchor_cache[resolved]:
                problems.append(f"{relative}:{number}: no such anchor: {target}")
    return problems


def main() -> int:
    files = markdown_files()
    anchor_cache: dict[Path, set[str]] = {}
    problems: list[str] = []
    for path in files:
        problems.extend(check_file(path, anchor_cache))

    if problems:
        print(f"Broken internal links: {len(problems)}")
        for problem in problems:
            print(f"  {problem}")
        return 1

    print(f"Internal links resolve in all {len(files)} Markdown files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
