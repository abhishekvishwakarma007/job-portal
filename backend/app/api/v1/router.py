"""Aggregate router for API v1.

Every feature router is mounted here rather than in main.py, so that adding a
feature touches one file and the version prefix lives in exactly one place.
"""

from fastapi import APIRouter

from app.api.v1.routes import applications, auth, jobs

API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)

api_router.include_router(auth.router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
