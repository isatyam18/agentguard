"""Main API router combining all resource route modules."""

from fastapi import APIRouter

from agentguard.api.routes.analytics import router as analytics_router
from agentguard.api.routes.approvals import router as approvals_router
from agentguard.api.routes.audit import router as audit_router
from agentguard.api.routes.health import router as health_router
from agentguard.api.routes.policies import router as policies_router
from agentguard.api.routes.transactions import router as transactions_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(transactions_router)
api_router.include_router(policies_router)
api_router.include_router(approvals_router)
api_router.include_router(audit_router)
api_router.include_router(analytics_router)
