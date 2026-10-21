import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.readiness import database_ready

from app.config import settings
from app.routes import (
    auth_router,
    orders_router,
    products_router,
    security_router,
    users_router,
    webhooks_router,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="NT219 Capstone - Cloud API Security for SME",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.exception_handler(RequestValidationError)
async def controlled_validation_error(request: Request, exc: RequestValidationError):
    # Do not echo raw inputs (including secrets or non-finite JSON numbers).
    return JSONResponse(status_code=422, content={"detail": [
        {key: error[key] for key in ("loc", "msg", "type") if key in error}
        for error in exc.errors()
    ]})


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """
    Add security headers and request correlation ID to every response.
    """
    request_id = str(uuid.uuid4())

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}s"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Cache-Control"] = "no-store"
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
    response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"

    try:
        del response.headers["Server"]
    except KeyError:
        pass

    return response


PREFIX = settings.API_PREFIX

app.include_router(auth_router, prefix=PREFIX)
app.include_router(products_router, prefix=PREFIX)
app.include_router(orders_router, prefix=PREFIX)
app.include_router(users_router, prefix=PREFIX)
app.include_router(webhooks_router, prefix=PREFIX)
app.include_router(security_router, prefix=PREFIX)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health/ready", tags=["Health"])
def readiness_check():
    """Readiness requires a reachable DB at the image's migration head(s)."""
    if not database_ready():
        return JSONResponse(status_code=503, content={"status": "not_ready"})
    return {"status": "ready"}


@app.get("/", tags=["Root"])
def root():
    return {"message": "NT219 API - Cloud Security for SME"}
