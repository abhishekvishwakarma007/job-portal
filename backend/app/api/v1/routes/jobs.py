"""Job posting routes: HR create/update/delete, candidate browse.

Endpoints are added in the jobs slice.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])
