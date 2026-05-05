from __future__ import annotations

from app.db.models import RepositoryProfile
from app.services.no_brainer_scanner import (
    _detect_broken_link,
    _detect_missing_env_docs,
    _detect_missing_prerequisites,
    _detect_missing_test_command,
    _detect_no_troubleshooting,
    _detect_no_windows_notes,
)


def test_missing_env_docs():
    readme = "Configure your .env file."
    assert _detect_missing_env_docs(readme) is not None


def test_missing_env_docs_when_present():
    readme = "Set the FOO_API_KEY environment variable in your .env file."
    assert _detect_missing_env_docs(readme) is None


def test_broken_link():
    assert _detect_broken_link("[click me]()") is not None
    assert _detect_broken_link("[click me](TBD)") is not None
    assert _detect_broken_link("[click](https://x.example)") is None


def test_missing_test_command():
    prof = RepositoryProfile(repo_id=1, test_commands=["pytest"])
    assert _detect_missing_test_command(prof, "no mention") is not None
    assert _detect_missing_test_command(prof, "run pytest") is None


def test_missing_prerequisites():
    prof = RepositoryProfile(repo_id=1, prerequisites=[])
    assert _detect_missing_prerequisites(prof) is not None
    prof.prerequisites = ["python 3.11"]
    assert _detect_missing_prerequisites(prof) is None


def test_no_windows_notes():
    assert _detect_no_windows_notes("install on linux") is not None
    assert _detect_no_windows_notes("works on Windows / WSL") is None


def test_no_troubleshooting():
    assert _detect_no_troubleshooting("# Setup\n\ninstall") is not None
    assert _detect_no_troubleshooting("# Troubleshooting\n\n...") is None
