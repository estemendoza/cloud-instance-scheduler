import logging.config

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from app.api.v1.api import api_router
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.version import APP_VERSION
from app.services.scheduler import scheduler_service
from app.logging_config import LOGGING_CONFIG

# Configure logging with timestamps
logging.config.dictConfig(LOGGING_CONFIG)

_docs = not settings.DISABLE_DOCS
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=APP_VERSION,
    docs_url=f"{settings.API_V1_STR}/docs" if _docs else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if _docs else None,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if _docs else None,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configure CORS
# In production behind nginx proxy, requests are same-origin
# But we allow common development and deployment origins
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
# Allow any origin in production (nginx handles the proxying)
# This is safe because auth is handled via JWT/API keys
if settings.CORS_ALLOW_ALL_ORIGINS:
    cors_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True if cors_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)

MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    # Reject oversized request bodies (POST/PUT/PATCH)
    if request.method in ("POST", "PUT", "PATCH"):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large"},
            )

    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        "camera=(), microphone=(), geolocation=()"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

    return response


# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    return {"message": "Cloud Instance Scheduler API"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Start the scheduler on app startup."""
    scheduler_service.start()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the scheduler on app shutdown."""
    await scheduler_service.shutdown()
