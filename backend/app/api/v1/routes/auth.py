"""Authentication routes: registration, login, refresh, logout.

Endpoints are added in the auth slice; this module exists so the router tree
is wired and mounted from the very first commit.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])
