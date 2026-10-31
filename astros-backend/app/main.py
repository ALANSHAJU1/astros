from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session
from app.api.routes.admin_users import router as admin_users_router

# Import routers
from app.api.routes.database_recommendations import router as database_recommendations_router
from app.api.routes.events import router as events_router
from app.api.routes.recommendations import router as recommendations_router
from app.api.routes.visibility_assessments import router as visibility_assessments_router
from app.api.routes.environmental_observations import router as environmental_observations_router
from app.api.routes.observation_plans import router as observation_plans_router
from app.api.routes.auth import router as auth_router
from app.core.config import CORS_ALLOWED_ORIGINS, ENABLE_API_DOCS
from app.db.session import get_db

app = FastAPI(
    title="AstroOS Backend",
    version="1.0.0",
    description="Backend API for astronomical events and recommendations.",
    docs_url="/docs" if ENABLE_API_DOCS else None,
    redoc_url="/redoc" if ENABLE_API_DOCS else None,
)

# CORS: only enabled when at least one allowed origin is configured.
# In development, leave CORS_ALLOWED_ORIGINS unset (no cross-origin access needed).
# In production, set CORS_ALLOWED_ORIGINS=https://your-frontend.example.com
if CORS_ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

# Custom validation error handler: map 422 to 400 for observation‑plan endpoint (legacy behavior)
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Observation‑plan endpoint expects specific error when body is not a JSON object
    if request.url.path == "/api/v1/observation-plans/generate":
        for err in exc.errors():
            if err.get("type") in ("type_error.dict", "model_type", "dict_type") or "dictionary" in err.get("msg", "").lower():
                return JSONResponse(status_code=400, content={"detail": "Request body must be a JSON object"})
        return JSONResponse(status_code=400, content={"detail": "Invalid request body"})
    return JSONResponse(status_code=422, content={"detail": "Invalid request"})

# Register API routes
app.include_router(auth_router)
app.include_router(events_router)
app.include_router(recommendations_router)
app.include_router(database_recommendations_router)
app.include_router(visibility_assessments_router)
app.include_router(environmental_observations_router)
app.include_router(observation_plans_router)
app.include_router(admin_users_router)

@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "message": "AstroOS backend is running"}


@app.get("/health/db", tags=["Health"])
def database_health_check(db: Session = Depends(get_db)):
    """Database readiness probe. Returns 200 when the database is reachable, 503 otherwise.

    This endpoint is intended for load balancer and orchestrator readiness checks.
    It does not expose any internal configuration or credentials.
    """
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "reachable"}
    except (OperationalError, SQLAlchemyError):
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is not reachable",
        )
