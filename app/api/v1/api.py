from fastapi import APIRouter
from app.api.v1.endpoints import (
    users, auth, mfa, cloud_accounts, resources,
    policies, overrides, executions, savings,
    organizations, system, calculator, providers,
    pricing_jobs, audit_logs,
)

api_router = APIRouter()
api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(mfa.router, prefix="/auth", tags=["mfa"])
api_router.include_router(cloud_accounts.router,
                          prefix="/cloud-accounts", tags=["cloud-accounts"])
api_router.include_router(
    resources.router, prefix="/resources", tags=["resources"]
)
api_router.include_router(policies.router, prefix="/policies", tags=["policies"])
api_router.include_router(overrides.router, prefix="/overrides", tags=["overrides"])
api_router.include_router(
    executions.router, prefix="/executions", tags=["executions"]
)
api_router.include_router(savings.router, prefix="/savings", tags=["savings"])
api_router.include_router(organizations.router,
                          prefix="/organizations", tags=["organizations"])
api_router.include_router(
    calculator.router, prefix="/calculator", tags=["calculator"]
)
api_router.include_router(
    providers.router, prefix="/providers", tags=["providers"]
)
api_router.include_router(
    pricing_jobs.router, prefix="/pricing-jobs",
    tags=["pricing-jobs"],
)
api_router.include_router(
    audit_logs.router, prefix="/audit-logs",
    tags=["audit-logs"],
)
