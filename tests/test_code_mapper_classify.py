"""code_mapper file classification helpers."""

from __future__ import annotations

from app.services.code_mapper import _classify, _guess_lang_from_files


def test_classify():
    files = [
        "src/parser.py",
        "src/__init__.py",
        "tests/test_parser.py",
        "tests/conftest.py",
        "pyproject.toml",
        "README.md",
        "setup.py",
        "src/cli.py",
    ]
    cls = _classify(files)
    assert "tests/test_parser.py" in cls["test_files"]
    assert "pyproject.toml" in cls["config_files"]
    assert "src" in cls["source_dirs"]


def test_guess_python():
    files = [f"src/m{i}.py" for i in range(8)]
    assert _guess_lang_from_files(files) == "python"


def test_guess_typescript():
    files = [f"src/m{i}.ts" for i in range(8)]
    assert _guess_lang_from_files(files) == "typescript"


def test_guess_other():
    files = ["README.md", "LICENSE"]
    assert _guess_lang_from_files(files) == "other"
