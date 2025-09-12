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
from app.database import engine
from app.database import Base

# Setup logging before creating the app
setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "logs/app.log"),
    enable_console=True
)

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Application startup initiated")
    
    try:
        # Create database tables
        logger.info("Creating database tables")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        
        # Add any other startup tasks here
        # - Initialize Redis connection
        # - Setup job queue workers
        # - Load configuration
        
        logger.info("Application startup completed successfully")
        yield
        
    except Exception as e:
        logger.error("Application startup failed", error=str(e), exc_info=True)
        raise
    
    finally:
        # Shutdown
        logger.info("Application shutdown initiated")
        
        # Add cleanup tasks here
        # - Close database connections
        # - Shutdown job queue workers
        # - Save final state
        
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
    * 1000 requests per hour per API key
    * 100 submissions per hour per affiliate
    
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
    return {
        "status": "healthy",
        "service": "affiliate-reconciliation-platform",
        "version": "1.0.0",
        "timestamp": time.time()
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
    
    # Add more health checks here
    # - Redis connection
    # - External API connectivity
    # - File system access
    
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
