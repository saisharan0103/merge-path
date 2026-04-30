from pathlib import Path


class RepoScanner:
    def scan(self, repo_path: Path) -> dict[str, object]:
        files = self._files(repo_path)
        names = {path.name.lower() for path in files}
        rel_paths = {self._rel(repo_path, path).lower() for path in files}

        return {
            "local_path": str(repo_path),
            "is_cloned": (repo_path / ".git").exists(),
            "tech_stack": self._tech_stack(files, names, rel_paths),
            "package_manager": self._package_manager(names),
            "has_test_config": self._has_test_config(repo_path, names, rel_paths),
            "has_lint_config": self._has_lint_config(names, rel_paths),
            "has_build_config": self._has_build_config(names, rel_paths),
            "contribution_docs": self._contribution_docs(files, repo_path),
            "important_files": self._important_files(files, repo_path),
        }

    def _files(self, repo_path: Path) -> list[Path]:
        ignored_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "target"}
        result: list[Path] = []
        for path in repo_path.rglob("*"):
            if len(result) >= 500:
                break
            if any(part in ignored_dirs for part in path.parts):
                continue
            if path.is_file():
                result.append(path)
        return result

    def _tech_stack(self, files: list[Path], names: set[str], rel_paths: set[str]) -> list[str]:
        stack: list[str] = []
        suffixes = {path.suffix.lower() for path in files}
        if {"pyproject.toml", "requirements.txt", "setup.py"} & names or ".py" in suffixes:
            stack.append("Python")
        if {"package.json", "tsconfig.json"} & names or {".js", ".jsx", ".ts", ".tsx"} & suffixes:
            stack.append("JavaScript/TypeScript")
        if "go.mod" in names or ".go" in suffixes:
            stack.append("Go")
        if "cargo.toml" in names or ".rs" in suffixes:
            stack.append("Rust")
        if {"pom.xml", "build.gradle", "build.gradle.kts"} & names or {".java", ".kt"} & suffixes:
            stack.append("Java/Kotlin")
        if any(path.endswith(".csproj") or path.endswith(".sln") for path in rel_paths):
            stack.append(".NET")
        return stack or ["Unknown"]

    def _package_manager(self, names: set[str]) -> str | None:
        if "pnpm-lock.yaml" in names:
            return "pnpm"
        if "yarn.lock" in names:
            return "yarn"
        if "package-lock.json" in names:
            return "npm"
        if "poetry.lock" in names:
            return "poetry"
        if "uv.lock" in names:
            return "uv"
        if "pyproject.toml" in names:
            return "pyproject"
        if "requirements.txt" in names:
            return "pip"
        if "go.mod" in names:
            return "go"
        if "cargo.toml" in names:
            return "cargo"
        if "pom.xml" in names:
            return "maven"
        if "build.gradle" in names or "build.gradle.kts" in names:
            return "gradle"
        return None

    def _has_test_config(self, repo_path: Path, names: set[str], rel_paths: set[str]) -> bool:
        test_files = {
            "pytest.ini",
            "tox.ini",
            "noxfile.py",
            "jest.config.js",
            "jest.config.ts",
            "vitest.config.js",
            "vitest.config.ts",
            "playwright.config.js",
            "playwright.config.ts",
        }
        return bool(test_files & names or "tests" in {path.name.lower() for path in repo_path.iterdir() if path.is_dir()} or "test" in rel_paths)

    def _has_lint_config(self, names: set[str], rel_paths: set[str]) -> bool:
        lint_files = {
            ".flake8",
            "ruff.toml",
            ".ruff.toml",
            ".pylintrc",
            ".eslintrc",
            ".eslintrc.js",
            ".eslintrc.json",
            "eslint.config.js",
            "eslint.config.mjs",
            "biome.json",
        }
        return bool(lint_files & names or ".prettierrc" in names or "pyproject.toml" in names or any("golangci" in path for path in rel_paths))

    def _has_build_config(self, names: set[str], rel_paths: set[str]) -> bool:
        build_files = {
            "pyproject.toml",
            "setup.py",
            "package.json",
            "vite.config.js",
            "vite.config.ts",
            "webpack.config.js",
            "dockerfile",
            "makefile",
            "go.mod",
            "cargo.toml",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
        }
        return bool(build_files & names or any(path.endswith(".csproj") or path.endswith(".sln") for path in rel_paths))

    def _contribution_docs(self, files: list[Path], repo_path: Path) -> list[str]:
        prefixes = ("contributing", "code_of_conduct", "security")
        return [
            self._rel(repo_path, path)
            for path in files
            if path.name.lower().startswith(prefixes) or ".github/issue_template" in self._rel(repo_path, path).lower()
        ][:20]

    def _important_files(self, files: list[Path], repo_path: Path) -> list[str]:
        important = {
            "readme.md",
            "contributing.md",
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "go.mod",
            "cargo.toml",
            "pom.xml",
            "dockerfile",
            "makefile",
            ".github/workflows",
        }
        found: list[str] = []
        for path in files:
            rel = self._rel(repo_path, path)
            lower = rel.lower()
            if path.name.lower() in important or lower.startswith(".github/workflows/"):
                found.append(rel)
        return found[:40]

    @staticmethod
    def _rel(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()
