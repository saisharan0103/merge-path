"""Auth shim — single-user, no JWT.

Per `DECISIONS.md`: no auth at all. We expose ``GET /auth/me`` only because
the frontend wants to render the current user; ``POST /auth/login`` is kept
as a no-op for compat (returns the seeded user).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db

router = APIRouter()


def current_user(db: Session = Depends(get_db)) -> User:
    user = db.query(User).first()
    if user is None:
        raise RuntimeError("no seed user — startup did not complete")
    return user


@router.get("/auth/me")
def me(user: User = Depends(current_user)) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "github_username": user.github_username,
        "has_pat": user.github_pat_encrypted is not None,
    }


@router.post("/auth/login")
def login(user: User = Depends(current_user)) -> dict:
    """No-op kept for spec compatibility — single-user, no auth."""
    return {
        "access_token": "local",
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email},
    }
