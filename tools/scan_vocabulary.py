"""Vocabulary and typography scan for the epicormic paper repository.

Rejects em-dashes, en-dashes, curly quotes, and the words listed in
tools/banned_words.txt. Markdown and TeX files are scanned in full. Python
files are scanned only in their comments and string literals (which includes
docstrings), so an identifier imported from a third-party package never
trips the scan. Notebooks are scanned cell by cell: markdown cells in full,
code cells as Python with IPython magic and shell lines ignored, raw cells
not at all. Bibliography files are not scanned, because cited titles are
someone else's words.

Usage:
    python tools/scan_vocabulary.py            # scan the repository
    python tools/scan_vocabulary.py PATH ...   # scan the given files or directories

Exit status is 1 when any hit is found, 0 otherwise.
"""

from __future__ import annotations

import io
import json
import re
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BANNED_WORDS_FILE = REPO_ROOT / "tools" / "banned_words.txt"
SCANNED_SUFFIXES = {".md", ".py", ".ipynb", ".tex"}
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "dist",
    "build",
    ".hypothesis",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
    "__pycache__",
    "htmlcov",
    "stores",
}
TYPOGRAPHY = {
    "\u2014": "em-dash",
    "\u2013": "en-dash",
    "\u2018": "curly single quote",
    "\u2019": "curly single quote",
    "\u201c": "curly double quote",
    "\u201d": "curly double quote",
}


def load_banned_word_list(path: Path = BANNED_WORDS_FILE) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def load_banned_words(path: Path = BANNED_WORDS_FILE) -> re.Pattern[str]:
    alternation = "|".join(re.escape(word) for word in load_banned_word_list(path))
    return re.compile(rf"(?<![\w-])(?:{alternation})(?![\w-])", re.IGNORECASE)


def scan_text(text: str, pattern: re.Pattern[str], first_line: int = 1) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    for offset, line in enumerate(text.splitlines()):
        number = first_line + offset
        for match in pattern.finditer(line):
            hits.append((number, f"banned word '{match.group(0)}'"))
        for char, name in TYPOGRAPHY.items():
            if char in line:
                hits.append((number, name))
    return hits


def scan_markdown(path: Path, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    return scan_text(path.read_text(encoding="utf-8"), pattern)


def scan_python_source(source: str, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        for token in tokens:
            if token.type in (tokenize.COMMENT, tokenize.STRING):
                hits.extend(scan_text(token.string, pattern, first_line=token.start[0]))
    except tokenize.TokenError as error:
        hits.append((0, f"could not tokenize: {error}"))
    return hits


def scan_python(path: Path, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    return scan_python_source(path.read_text(encoding="utf-8"), pattern)


def _neutralize_magics(source: str) -> str:
    """Turn IPython magic and shell lines into comments so the tokenizer accepts them."""
    lines = []
    for line in source.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("%", "!")):
            lines.append("# " + line)
        else:
            lines.append(line)
    return "\n".join(lines) + "\n"


def scan_notebook(path: Path, pattern: re.Pattern[str]) -> list[tuple[int, str]]:
    """Scan a notebook; the reported line number is the 1-based cell index."""
    document = json.loads(path.read_text(encoding="utf-8"))
    hits: list[tuple[int, str]] = []
    for index, cell in enumerate(document.get("cells", []), start=1):
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        kind = cell.get("cell_type")
        if kind == "markdown":
            cell_hits = scan_text(source, pattern)
        elif kind == "code":
            cell_hits = scan_python_source(_neutralize_magics(source), pattern)
        else:
            continue
        hits.extend((index, f"cell {index} line {line}: {reason}") for line, reason in cell_hits)
    return hits


SCANNERS = {
    ".md": scan_markdown,
    ".tex": scan_markdown,
    ".py": scan_python,
    ".ipynb": scan_notebook,
}


def iter_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        if root.is_file():
            files.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SCANNED_SUFFIXES and path.is_file():
                files.append(path)
    return [path for path in files if path.resolve() != BANNED_WORDS_FILE.resolve()]


def main(argv: list[str]) -> int:
    pattern = load_banned_words()
    roots = [Path(arg) for arg in argv] or [REPO_ROOT]
    total = 0
    for path in iter_files(roots):
        scanner = SCANNERS.get(path.suffix)
        if scanner is None:
            continue
        hits = scanner(path, pattern)
        shown = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        for line, reason in hits:
            total += 1
            print(f"{shown}:{line}: {reason}")
    if total:
        print(f"{total} hit(s)")
        return 1
    print("vocabulary scan clean")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
