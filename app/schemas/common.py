"""Shared schema fragments."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    page_size: int = 20


class ErrorEnvelope(BaseModel):
    error: str
    message: str
    details: dict | None = None
