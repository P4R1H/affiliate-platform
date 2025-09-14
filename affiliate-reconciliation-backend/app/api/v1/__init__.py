"""
API v1 router initialization and setup.
"""
from fastapi import APIRouter
from .endpoints import campaigns, users, clients, submissions, reconciliation, alerts, platforms, analytics

api_router = APIRouter()

api_router.include_router(
    campaigns.router, 
    prefix="/campaigns", 
    tags=["campaigns"]
)

api_router.include_router(
    users.router, 
    prefix="/users", 
    tags=["users"]
)

api_router.include_router(
    clients.router, 
    prefix="/clients", 
    tags=["clients"]
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

api_router.include_router(
    analytics.router,
    prefix="/analytics",
    tags=["analytics"]
)

