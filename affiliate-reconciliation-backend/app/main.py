"""
FastAPI application main module.
Enterprise-grade setup with comprehensive middleware, error handling, and observability.
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time
import uuid
import os
from contextlib import asynccontextmanager
from app.api.v1 import api_router
from app.utils import setup_logging, get_logger
from app.jobs.queue import PriorityDelayQueue  # queue infra
from app.jobs.worker_reconciliation import ReconciliationWorker, create_queue
from app.jobs.reconciliation_job import ReconciliationJob
from app.database import engine
from app.database import Base
from app.config import QUEUE_SETTINGS, RATE_LIMIT_SETTINGS
from app.utils.ratelimiter import rate_limiter
from app.models.db.enums import UserRole
from app.database import SessionLocal
from app.models.db import User

# Setup logging before creating the app
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "logs/app.log"),
    enable_console=True
)

logger = get_logger(__name__)

_queue = None
_worker: ReconciliationWorker | None = None


def enqueue_reconciliation(affiliate_report_id: int, priority: str = "normal", delay_seconds: float = 0.0) -> None:
    """Enqueue a reconciliation job for the given affiliate report.

    Args:
        affiliate_report_id: The ID of the affiliate report to reconcile.
        priority: Job priority level ('high', 'normal', 'low').
        delay_seconds: Delay before the job becomes available for processing.
    """
    if _queue is None:
        raise RuntimeError("Queue not initialized")
    job = ReconciliationJob(affiliate_report_id=affiliate_report_id, priority=priority)
    _queue.enqueue(job, priority=priority, delay_seconds=delay_seconds)
    logger.info(
        "Enqueued reconciliation job", report_id=affiliate_report_id, priority=priority, delay=delay_seconds
    )


def check_redis_health() -> bool:
    """Check if Redis is available for queue operations."""
    try:
        import redis
        redis_url = str(QUEUE_SETTINGS.get("redis_url", "redis://localhost:6379/0"))
        timeout = float(QUEUE_SETTINGS.get("redis_health_check_timeout", 2.0))  # type: ignore[arg-type]
        
        # Try to connect and ping Redis
        redis_client = redis.from_url(redis_url, socket_connect_timeout=timeout)
        redis_client.ping()
        logger.info("Redis health check: Redis is available", url=redis_url)
        return True
    except (ImportError, Exception) as e:
        logger.warning("Redis health check: Redis is unavailable", error=str(e))
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Application startup initiated")
    
    global _queue, _worker
    try:
        # Create database tables
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")

        # Check Redis health if Redis queue is enabled
        use_redis = QUEUE_SETTINGS.get("use_redis", False)  # type: ignore[assignment]
        if use_redis:
            redis_available = check_redis_health()
            if redis_available:
                logger.info("Redis queue will be used for job processing")
            else:
                logger.warning("Redis queue is enabled but Redis is unavailable. Using in-memory queue as fallback.")
        
        # Initialize queue and worker
        _queue = create_queue()
        # expose queue in app state for endpoints to enqueue jobs without importing main (avoid circular)
        app.state.reconciliation_queue = _queue  # type: ignore[attr-defined]
        _worker = ReconciliationWorker(_queue)
        _worker.start()
        logger.info("Reconciliation queue + worker started")
        
        # Start Discord bot (non-blocking) if explicitly enabled
        try:
            from app.config import ENABLE_DISCORD_BOT
            if ENABLE_DISCORD_BOT:
                from app.services.discord_bot import start_discord_bot  # local import to avoid unnecessary dependency load
                await start_discord_bot()
            else:
                logger.info("Discord bot not enabled; skipping bot startup")
        except Exception as e:  # pragma: no cover
            logger.error("Discord bot startup check failed", error=str(e), exc_info=True)
        logger.info("Application startup completed successfully")
        yield
    except Exception as e:  # pragma: no cover
        logger.error("Application startup failed", error=str(e), exc_info=True)
        raise
    finally:
        logger.info("Application shutdown initiated")
        if _worker:
            _worker.stop()
            logger.info("Reconciliation worker stop signal sent")
        # Shutdown discord bot if it was started
        try:
            from app.config import ENABLE_DISCORD_BOT
            if ENABLE_DISCORD_BOT:
                from app.services.discord_bot import stop_discord_bot  # local import
                await stop_discord_bot()
        except Exception as e:  # pragma: no cover
            logger.error("Discord bot shutdown failed", error=str(e), exc_info=True)
        logger.info("Application shutdown completed")

# FastAPI app initialization with comprehensive configuration
app = FastAPI(
    title="Affiliate Reconciliation Platform",
    description="""
    Enterprise-grade affiliate marketing data reconciliation system.
    
    ## Features
    * **Multi-platform integration** - Support for Reddit, Instagram, Meta
    * **Dual submission modes** - API and Discord-like submissions
    * **Real-time reconciliation** - Automated data verification
    * **Trust scoring** - Affiliate reliability tracking
    * **Unified dashboards** - Consolidated reporting views
    * **Comprehensive alerting** - Data quality monitoring
    
    ## Authentication
    Use Bearer token authentication with your affiliate API key:
    ```
    Authorization: Bearer aff_your_api_key_here
    ```
    
    ## Rate Limiting
    Per-API key limits with categories (see API docs for full details). Standard headers:
    `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
    Defaults: generic=1000/hr, submissions=100/hr, recon triggers=10/min, recon queries=100/min.
    
    ## Support
    For technical support, contact: support@affiliate-platform.com
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
    # Add API metadata
    contact={
        "name": "Affiliate Platform Team",
        "email": "support@affiliate-platform.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# CORS middleware - configure appropriately for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compression middleware for better performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Rate limiting middleware (must run after request context logging to reuse request_id)
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Apply per-API key rate limits with endpoint categorization.

    Categories mapping (prefix-based):
      /api/v1/submissions -> submission
      /api/v1/reconciliation/run -> recon_trigger (POST)
      /api/v1/reconciliation/(results|logs|queue) -> recon_query
    Fallback: default

    Role overrides (RATE_LIMIT_SETTINGS['role_overrides']) adjust *default* limit only.
    """
    path = request.url.path
    method = request.method.upper()
    category = "default"
    if path.startswith("/api/v1/submissions"):
        category = "submission"
    elif path.startswith("/api/v1/reconciliation/run") and method == "POST":
        category = "recon_trigger"
    elif path.startswith("/api/v1/reconciliation/") and any(x in path for x in ["results", "logs", "queue"]):
        category = "recon_query"

    settings = RATE_LIMIT_SETTINGS.get(category, RATE_LIMIT_SETTINGS["default"])
    limit = int(settings.get("limit", 1000))  # type: ignore[arg-type]
    window_seconds = int(settings.get("window_seconds", 3600))  # type: ignore[arg-type]

    # Extract API key / bot token for keying. If absent, treat as anonymous (optional: skip limiting)
    auth_header = request.headers.get("Authorization", "")
    api_key = None
    if auth_header.startswith("Bearer "):
        api_key = auth_header[7:]
    elif auth_header.startswith("Bot "):
        # Bot submissions still apply submission category limit keyed by discord user if provided
        discord_id = request.headers.get("X-Discord-User-ID", "bot")
        api_key = f"bot:{discord_id}"
    else:
        # Health/root docs etc; we can bypass strict enforcement but still apply a shared key
        api_key = "public"

    # Role override only for default category (makes generic limit larger for privileged roles)
    if category == "default" and auth_header.startswith("Bearer "):
        # Minimal DB lookup to get role (avoid re-query duplication with dependency). Acceptable cost.
        db = None
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.api_key == api_key, User.is_active == True).first()  # type: ignore[arg-type]
            if user:
                role_overrides = RATE_LIMIT_SETTINGS.get("role_overrides", {})  # type: ignore[assignment]
                override = role_overrides.get(user.role.value) if hasattr(user.role, "value") else role_overrides.get(str(user.role))
                if override:
                    limit = int(override)
        except Exception:
            pass
        finally:
            if db is not None:
                try:
                    db.close()
                except Exception:
                    pass

    allowed, meta = await rate_limiter.check_and_increment(api_key, category, limit, window_seconds)

    if not allowed:
        # Build 429 with headers
        from fastapi.responses import JSONResponse
        resp = JSONResponse(
            status_code=429,
            content={
                "success": False,
                "message": f"Rate limit exceeded for category '{category}'",
                "category": category,
            },
        )
        resp.headers["X-RateLimit-Limit"] = str(meta["limit"])
        resp.headers["X-RateLimit-Remaining"] = "0"
        resp.headers["X-RateLimit-Reset"] = str(meta["reset_epoch"])
        return resp

    # Proceed
    response = await call_next(request)
    response.headers["X-RateLimit-Limit"] = str(meta["limit"])
    response.headers["X-RateLimit-Remaining"] = str(meta["remaining"])
    response.headers["X-RateLimit-Reset"] = str(meta["reset_epoch"])
    return response

# Request ID and comprehensive logging middleware
@app.middleware("http")
async def add_request_context_and_logging(request: Request, call_next):
    """
    Add request ID, timing, and comprehensive request/response logging.
    """
    # Generate or extract request ID
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Add security headers
    request.state.start_time = time.time()
    
    # Log incoming request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        user_agent=request.headers.get("User-Agent"),
        remote_addr=request.client.host if request.client else "unknown",
        request_id=request_id
    )
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - request.state.start_time
    
    # Add response headers
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(round(process_time * 1000, 2))
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Log response
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
        process_time_ms=round(process_time * 1000, 2),
        request_id=request_id
    )
    
    return response

# Custom exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        "Request validation failed",
        errors=exc.errors(),
        request_id=request_id,
        url=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": "Request validation failed",
            "details": exc.errors(),
            "request_id": request_id
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.warning(
        "HTTP exception",
        status_code=exc.status_code,
        detail=exc.detail,
        request_id=request_id,
        url=str(request.url),
        method=request.method
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "request_id": request_id
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    
    logger.error(
        "Unhandled exception",
        error=str(exc),
        error_type=type(exc).__name__,
        request_id=request_id,
        url=str(request.url),
        method=request.method,
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "request_id": request_id
        }
    )

# Health check endpoints
@app.get("/health", tags=["health"], summary="Basic health check")
async def health_check():
    """Basic health check endpoint for load balancers."""
    # Minimal but now includes queue backend + redis status if enabled
    use_redis = bool(QUEUE_SETTINGS.get("use_redis", False))  # type: ignore[arg-type]
    redis_status = None
    queue_backend = "redis" if use_redis else "memory"
    if use_redis:
        redis_status = "healthy" if check_redis_health() else "unavailable"
    return {
        "status": "healthy",
        "service": "affiliate-reconciliation-platform",
        "version": "1.0.0",
        "timestamp": time.time(),
        "queue_backend": queue_backend,
        **({"redis_status": redis_status} if redis_status is not None else {}),
    }

@app.get("/health/detailed", tags=["health"], summary="Detailed health check")
async def detailed_health_check():
    """Detailed health check with database and external service status."""
    health_status = {
        "status": "healthy",
        "service": "affiliate-reconciliation-platform",
        "version": "1.0.0",
        "timestamp": time.time(),
        "checks": {}
    }
    
    # Database check
    try:
        from app.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Redis check (only if configured to use redis queue)
    use_redis = bool(QUEUE_SETTINGS.get("use_redis", False))  # type: ignore[arg-type]
    if use_redis:
        try:
            healthy = check_redis_health()
            health_status["checks"]["redis"] = "healthy" if healthy else "unavailable"
            if not healthy and health_status["status"] == "healthy":
                health_status["status"] = "degraded"
        except Exception as e:  # pragma: no cover
            health_status["checks"]["redis"] = f"error: {e}"  # noqa: E501
            health_status["status"] = "degraded"

    # Queue snapshot (non-blocking) for visibility
    try:
        queue = getattr(app.state, "reconciliation_queue", None)  # type: ignore[attr-defined]
        if queue is not None:
            snap = queue.snapshot()
            # Avoid dumping potentially large internals
            health_status["checks"]["queue"] = {
                k: v for k, v in snap.items() if k in {"depth", "ready", "scheduled", "redis_active"}
            }
    except Exception:  # pragma: no cover
        pass
    
    return health_status

# API Documentation root
@app.get("/", tags=["root"])
async def root():
    """API root endpoint with basic information."""
    return {
        "message": "Affiliate Reconciliation Platform API",
        "version": "1.0.0",
        "documentation": "/docs",
        "health_check": "/health",
        "api_base": "/api/v1"
    }

# Include API router with version prefix
app.include_router(api_router, prefix="/api/v1")

# Development server configuration
if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting development server")
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        log_level="info",
        access_log=True
    )
