# =========================================================
# ApexDeploy - FastAPI Application Entry Point
# Initializes server, configures middlewares and routers
# =========================================================

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.router import api_router
from src.config.logging_config import setup_logging
from src.config.settings import settings
from src.core.exceptions import ApexException
from src.db.database import run_migrations, verify_tables

# Set up logging early during execution
setup_logging()
logger = logging.getLogger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events manager handling backend startup and shutdown hooks."""
    logger.info(f"Starting {settings.APP_NAME} in environment: {settings.APP_ENV}")
    
    # 1. Ensure runtime directories exist
    settings.workspaces_path.mkdir(parents=True, exist_ok=True)
    settings.artifacts_path.mkdir(parents=True, exist_ok=True)
    settings.logs_path.mkdir(parents=True, exist_ok=True)
    
    # 2. Database migrations and component setups
    try:
        await run_migrations()
        await verify_tables()
        
        # Initialize event bus handlers and agent orchestrator
        from src.events.handlers import register_core_event_handlers
        from src.core.orchestrator import orchestrator
        
        register_core_event_handlers()
        orchestrator.initialize()
        
    except Exception as e:
        logger.critical(f"Database/component initialization failed: {e}. Exiting.", exc_info=True)
        
    yield
    
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    description="Autonomous Git-to-Cloud Resilience Engineer API",
    version=settings.APP_VERSION,
    debug=settings.APP_DEBUG,
    lifespan=lifespan
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# Global Custom Exception Handler
@app.exception_handler(ApexException)
async def apex_exception_handler(request: Request, exc: ApexException):
    """Maps custom internal exceptions to API JSON responses."""
    logger.error(f"Internal Exception Intercepted on {request.url.path}: {exc.message}", exc_info=True)
    
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    # Map specific exceptions to HTTP codes
    exception_name = type(exc).__name__
    if exception_name == "ResourceNotFoundException":
        status_code = status.HTTP_404_NOT_FOUND
    elif exception_name == "ConfigurationException":
        status_code = status.HTTP_400_BAD_REQUEST
    elif exception_name == "DatabaseException":
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "error": exception_name,
            "message": exc.message,
            "details": exc.details
        }
    )


# Standard Python exception handler (catch-all)
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions to prevent leakage of traceback internals."""
    logger.error(f"Unhandled system error on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please contact the administrator."
        }
    )


# Mount main API routing table
app.include_router(api_router)


# Root fallback endpoint
@app.get("/")
async def root():
    return {
        "message": f"Welcome to the {settings.APP_NAME} API",
        "docs": "/docs",
        "health": "/api/health",
        "version": settings.APP_VERSION
    }
