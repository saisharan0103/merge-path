"""Structured logger setup. Use stdlib logging; one global logger named 'patchpilot'."""

from __future__ import annotations

import logging
import sys

from app.config import settings


def configure_logging(level: str | None = None) -> None:
    lvl = (level or settings.log_level).upper()
    handler = logging.StreamHandler(sys.stdout)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(lvl)

    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("urllib3").setLevel("WARNING")


def get_logger(name: str = "patchpilot") -> logging.Logger:
    return logging.getLogger(name)
