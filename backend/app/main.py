import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.api.v1.router import api_router
from app.services.assessment_service import DomainError

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.seed_default_assessments:
        from app.seed import seed_default_assessments

        with SessionLocal() as db:
            seed_default_assessments(db)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Database-backed placement readiness assessment API.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Candidate-Token", "Idempotency-Key"],
    expose_headers=["X-Request-ID"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID")
    try:
        request_id = str(uuid.UUID(request_id)) if request_id else str(uuid.uuid4())
    except ValueError:
        request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(DomainError)
async def handle_domain_error(request: Request, error: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {"code": error.code, "message": error.message, "details": []},
            "request_id": request.state.request_id,
        },
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(
    request: Request,
    error: RequestValidationError,
) -> JSONResponse:
    details = [
        {"field": ".".join(str(part) for part in item["loc"]), "message": item["msg"]}
        for item in error.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "The request did not match the required format.",
                "details": details,
            },
            "request_id": request.state.request_id,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        content={
            "error": {"code": "http_error", "message": str(error.detail), "details": []},
            "request_id": request.state.request_id,
        },
        headers=error.headers,
    )


@app.get("/health", tags=["operations"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["operations"])
def readiness() -> JSONResponse:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "dependency": "database"},
        )
    return JSONResponse(status_code=200, content={"status": "ready"})
