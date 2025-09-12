"""
API v1 router initialization and setup.
"""
from fastapi import APIRouter
from .endpoints import campaigns, affiliates, submissions, reconciliation, alerts, platforms

# Create the main API router for version 1
api_router = APIRouter()

# Include all endpoint routers with proper prefixes and tags
api_router.include_router(
    campaigns.router, 
    prefix="/campaigns", 
    tags=["campaigns"]
)

api_router.include_router(
    affiliates.router, 
    prefix="/affiliates", 
    tags=["affiliates"]
)

api_router.include_router(
    submissions.router, 
    prefix="/submissions", 
    tags=["submissions"]
)

api_router.include_router(
    platforms.router, 
    prefix="/platforms", 
    tags=["platforms"]
)

api_router.include_router(
    reconciliation.router, 
    prefix="/reconciliation", 
    tags=["reconciliation"]
)

api_router.include_router(
    alerts.router, 
    prefix="/alerts", 
    tags=["alerts"]
)

