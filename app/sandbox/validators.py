"""Per-stack validation command sets — see policies/validation_policy.md."""

from __future__ import annotations

DEFAULT_TIMEOUTS = {
    "python": 600,
    "javascript": 600,
    "typescript": 600,
    "go": 300,
    "rust": 1800,
    "java-maven": 900,
    "java-gradle": 900,
}

_DEFAULT_COMMANDS: dict[str, dict[str, list[str]]] = {
    "python": {
        "install": [
            "pip install -e .[dev]",
            "pip install -r requirements-dev.txt",
            "pip install -r requirements.txt",
            "poetry install",
        ],
        "test": ["pytest -x", "python -m pytest -x", "python -m unittest"],
        "lint": ["ruff check .", "flake8"],
        "typecheck": ["mypy ."],
        "build": ["python -m build"],
    },
    "javascript": {
        "install": ["npm ci", "npm install", "pnpm install --frozen-lockfile", "yarn install --frozen-lockfile"],
        "test": ["npm test"],
        "lint": ["npm run lint"],
        "typecheck": [],
        "build": ["npm run build"],
    },
    "typescript": {
        "install": ["pnpm install --frozen-lockfile", "npm ci", "npm install"],
        "test": ["pnpm test", "npm test"],
        "lint": ["pnpm lint", "npm run lint"],
        "typecheck": ["pnpm typecheck", "tsc --noEmit"],
        "build": ["pnpm build", "npm run build"],
    },
    "go": {
        "install": ["go mod download"],
        "test": ["go test ./..."],
        "lint": ["go vet ./..."],
        "typecheck": [],
        "build": ["go build ./..."],
    },
    "rust": {
        "install": ["cargo fetch"],
        "test": ["cargo test --all"],
        "lint": ["cargo clippy --all-targets -- -D warnings"],
        "typecheck": ["cargo check --all-targets"],
        "build": ["cargo build"],
    },
    "java-maven": {
        "install": ["mvn -B -DskipTests dependency:resolve"],
        "test": ["mvn -B test"],
        "lint": ["mvn -B checkstyle:check"],
        "typecheck": [],
        "build": ["mvn -B package -DskipTests"],
    },
    "java-gradle": {
        "install": ["./gradlew dependencies"],
        "test": ["./gradlew test"],
        "lint": ["./gradlew check"],
        "typecheck": [],
        "build": ["./gradlew build -x test"],
    },
}


def commands_for(stack: str, kind: str) -> list[str]:
    return _DEFAULT_COMMANDS.get(stack, {}).get(kind, [])
