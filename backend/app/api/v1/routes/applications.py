"""Application routes: candidate apply, HR review and status updates.

Endpoints are added in the applications slice.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/applications", tags=["applications"])
