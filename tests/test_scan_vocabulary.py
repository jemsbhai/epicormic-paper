"""The vocabulary scan covers Markdown, Python, TeX, and notebooks.

The banned words used as fixtures are drawn from the word list at test time,
so this file never spells one of them and the repository scan stays clean.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parent.parent / "tools" / "scan_vocabulary.py"


@pytest.fixture(scope="module")
def scan() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scan_vocabulary", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def words(scan: ModuleType) -> list[str]:
    """Four distinct banned words without hyphens, for fixtures."""
    plain = [word for word in scan.load_banned_word_list() if "-" not in word]
    assert len(plain) >= 4
    return plain[:4]


def _notebook(cells: list[dict[str, object]]) -> str:
    return json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5})


def test_word_list_is_non_empty_and_lower_case(scan: ModuleType) -> None:
    listed = scan.load_banned_word_list()
    assert listed
    assert all(word == word.strip() and word for word in listed)


def test_markdown_hits_report_line_and_reason(
    scan: ModuleType, words: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "note.md"
    path.write_text(f"fine line\nwe {words[0]} nothing \u2014 twice\n", encoding="utf-8")
    hits = scan.scan_markdown(path, scan.load_banned_words())
    assert hits == [(2, f"banned word '{words[0]}'"), (2, "em-dash")]


def test_match_is_case_insensitive_and_whole_word(
    scan: ModuleType, words: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "note.md"
    path.write_text(f"{words[1].upper()} here, but not x{words[1]}y\n", encoding="utf-8")
    hits = scan.scan_markdown(path, scan.load_banned_words())
    assert hits == [(1, f"banned word '{words[1].upper()}'")]


def test_tex_is_scanned_in_full(scan: ModuleType, words: list[str], tmp_path: Path) -> None:
    path = tmp_path / "section.tex"
    path.write_text(f"\\section{{Method}}\nA {words[0]} method.\n", encoding="utf-8")
    hits = scan.SCANNERS[".tex"](path, scan.load_banned_words())
    assert hits == [(2, f"banned word '{words[0]}'")]


def test_python_identifiers_are_ignored_but_strings_and_comments_are_not(
    scan: ModuleType, words: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "module.py"
    source = f'{words[0]} = 1\nx = "a {words[1]} join"\n# we {words[2]}\n'
    path.write_text(source, encoding="utf-8")
    hits = scan.scan_python(path, scan.load_banned_words())
    assert hits == [(2, f"banned word '{words[1]}'"), (3, f"banned word '{words[2]}'")]


def test_python_tokenize_error_is_reported(scan: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "broken.py"
    path.write_text('x = "unterminated\n', encoding="utf-8")
    hits = scan.scan_python(path, scan.load_banned_words())
    assert len(hits) == 1
    assert hits[0][0] == 0
    assert hits[0][1].startswith("could not tokenize")


def test_notebook_markdown_and_code_cells_are_scanned(
    scan: ModuleType, words: list[str], tmp_path: Path
) -> None:
    path = tmp_path / "study.ipynb"
    magics = f"%matplotlib inline\n!pip install x\n{words[3]} = 1\n"
    path.write_text(
        _notebook(
            [
                {"cell_type": "markdown", "source": ["clean\n", f"a {words[0]} cell\n"]},
                {"cell_type": "code", "source": magics},
                {"cell_type": "code", "source": [f"print('we {words[3]} it')\n"]},
                {"cell_type": "raw", "source": f"{words[0]} raw text is not scanned"},
            ]
        ),
        encoding="utf-8",
    )
    hits = scan.scan_notebook(path, scan.load_banned_words())
    assert hits == [
        (1, f"cell 1 line 2: banned word '{words[0]}'"),
        (3, f"cell 3 line 1: banned word '{words[3]}'"),
    ]


def test_iter_files_skips_ignored_directories_and_the_word_list(
    scan: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "keep.md").write_text("ok\n", encoding="utf-8")
    (tmp_path / "keep.tex").write_text("ok\n", encoding="utf-8")
    (tmp_path / "keep.ipynb").write_text(_notebook([]), encoding="utf-8")
    (tmp_path / "refs.bib").write_text("@article{x, title={Anything}}\n", encoding="utf-8")
    hidden = tmp_path / ".ipynb_checkpoints"
    hidden.mkdir()
    (hidden / "keep-checkpoint.ipynb").write_text(_notebook([]), encoding="utf-8")
    stores = tmp_path / "runs" / "stores"
    stores.mkdir(parents=True)
    (stores / "dump.md").write_text("ignored\n", encoding="utf-8")
    found = {path.name for path in scan.iter_files([tmp_path])}
    assert found == {"keep.md", "keep.tex", "keep.ipynb"}
    assert scan.iter_files([scan.BANNED_WORDS_FILE]) == []


def test_main_exit_codes(
    scan: ModuleType, words: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    clean = tmp_path / "clean.md"
    clean.write_text("nothing to see\n", encoding="utf-8")
    assert scan.main([str(clean)]) == 0
    assert "vocabulary scan clean" in capsys.readouterr().out

    dirty = tmp_path / "dirty.md"
    dirty.write_text(f"a {words[2]} \u201cquote\u201d\n", encoding="utf-8")
    assert scan.main([str(dirty)]) == 1
    out = capsys.readouterr().out
    assert f"banned word '{words[2]}'" in out
    assert "curly double quote" in out
    assert "3 hit(s)" in out


def test_main_ignores_a_file_with_an_unscanned_suffix(
    scan: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bib = tmp_path / "refs.bib"
    bib.write_text("@article{x, title={Anything}}\n", encoding="utf-8")
    assert scan.main([str(bib)]) == 0
    assert "vocabulary scan clean" in capsys.readouterr().out


def test_repository_is_clean(scan: ModuleType) -> None:
    assert scan.main([]) == 0
