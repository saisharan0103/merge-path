"""profiler internal helpers."""

from __future__ import annotations

from app.services.profiler import (
    _commands_for,
    _detect_stacks,
    _prerequisites,
    _summary,
)


class _GH:
    def __init__(self, files):
        self._files = files

    def get_file(self, _full, path):
        return self._files.get(path)


def test_detect_typescript():
    gh = _GH({"package.json": '{"scripts":{"test":"jest"}}', "tsconfig.json": "{}"})
    primary, stacks, files = _detect_stacks(gh, "x/y")
    assert primary == "typescript"
    assert "package.json" in files


def test_detect_python():
    gh = _GH({"pyproject.toml": "[project]\nname='demo'\n"})
    primary, _, _ = _detect_stacks(gh, "x/y")
    assert primary == "python"


def test_detect_go():
    gh = _GH({"go.mod": "module x"})
    primary, _, _ = _detect_stacks(gh, "x/y")
    assert primary == "go"


def test_detect_rust():
    gh = _GH({"Cargo.toml": "[package]\nname='x'"})
    primary, _, _ = _detect_stacks(gh, "x/y")
    assert primary == "rust"


def test_detect_java_maven():
    gh = _GH({"pom.xml": "<project/>"})
    primary, _, _ = _detect_stacks(gh, "x/y")
    assert primary == "java"


def test_commands_for_python():
    out = _commands_for("python", {"pyproject.toml": "[]"})
    assert any("pip install" in c for c in out["install_commands"])
    assert "pytest -x" in out["test_commands"]


def test_commands_for_javascript():
    out = _commands_for("javascript", {"package.json": '{"scripts":{"test":"jest","lint":"eslint","build":"x"}}'})
    assert "npm test" in out["test_commands"][0]
    assert "lint" in out["lint_commands"][0]


def test_commands_for_go():
    out = _commands_for("go", {})
    assert out["test_commands"] == ["go test ./..."]


def test_commands_for_rust():
    out = _commands_for("rust", {})
    assert "cargo test --all" in out["test_commands"]


def test_commands_for_java_maven():
    out = _commands_for("java", {"pom.xml": "<x/>"})
    assert "mvn -B test" in out["test_commands"]


def test_commands_for_java_gradle():
    out = _commands_for("java", {"build.gradle": "x"})
    assert "./gradlew test" in out["test_commands"]


def test_prerequisites_extraction():
    readme = "## Requirements\n\n- Python 3.11+\n- pip\n\n## Install\n\nrun"
    pre = _prerequisites(readme)
    assert any("Python" in p for p in pre)


def test_summary_extracts_first_paragraph():
    readme = "# Title\n\nThis is the summary paragraph.\n\nMore text."
    assert _summary(readme).startswith("This is the summary")
