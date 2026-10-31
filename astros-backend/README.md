# AstroOS Backend

FastAPI backend for the AstroOS observation-planning system.

## Requirements

- Python 3.11+
- PostgreSQL 15+ (local or remote instance)

---

## Local Setup & Quickstart (Windows PowerShell)

All commands below assume you are in the `astros-backend` directory:
```powershell
Set-Location "C:\Users\alans\Desktop\AstroOS11\astros-backend"
```

### 1. Create and Activate Virtual Environment
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If script execution is disabled in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first).*

### 2. Install Dependencies
```powershell
.\venv\Scripts\python.exe -m pip install --upgrade pip
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template configuration file:
```powershell
Copy-Item .env.example .env
```
Open `.env` in an editor and set your actual PostgreSQL credentials in `DATABASE_URL` and `TEST_DATABASE_URL`.

### 4. Apply Database Migrations
Apply all schema revisions to your PostgreSQL database:
```powershell
.\venv\Scripts\alembic.exe upgrade head
```

### 5. Launch the Development Server
```powershell
.\venv\Scripts\uvicorn.exe app.main:app --reload --host 127.0.0.1 --port 8001
```
The API will be available at `http://127.0.0.1:8001`.

---

## Environment Variables Reference

AstroOS Backend reads configuration from the environment and from the local `.env` file via `python-dotenv` and `os.getenv`. See `.env.example` for a ready-to-copy template.

| Variable Name | Type | Default | Required? | Behavior & Purpose |
|---|---|---|---|---|
| `DATABASE_URL` | `str` | *None* | **Yes** | Primary PostgreSQL connection string (e.g. `postgresql+psycopg://user:pass@localhost:5432/astros_db`). The application raises a fail-fast `RuntimeError` at startup if unset. |
| `TEST_DATABASE_URL` | `str` | *None* | **Yes (for tests)** | Dedicated test PostgreSQL connection string. `tests/conftest.py` strictly validates that the database name ends with `astros_test_db` to protect production and development data from accidental drops/flushes. |
| `OPEN_METEO_BASE_URL` | `str` | `https://api.open-meteo.com/v1/forecast` | No | Base endpoint URL for Open-Meteo hourly weather queries. |
| `WEATHER_REQUEST_TIMEOUT_SECONDS` | `float` | `10.0` | No | Timeout in seconds for HTTP requests to the upstream Open-Meteo weather API. Timed out requests raise `WeatherProviderTimeoutError` (HTTP 504). |
| `WEATHER_CACHE_TTL_SECONDS` | `int` | `1800` | No | Duration in seconds (default: 30 minutes) to retain weather forecast results in the in-memory TTL cache. |
| `LIGHT_POLLUTION_DATA_PATH` | `str` | `""` (`None`) | No | File path to local SQM raster/grid dataset (.asc or .json). If unset, the service attempts to use DarkSkySites if configured. |
| `DARKSKYSITES_API_KEY` | `str` | `""` (`None`) | No | API key for DarkSkySites zenith SQM lookup. If neither this nor `LIGHT_POLLUTION_DATA_PATH` is provided, the light pollution service defaults to an unavailable provider status without crashing. |
| `DARKSKYSITES_BASE_URL` | `str` | `https://darkskysites.com/api/sqm` | No | Upstream API endpoint for DarkSkySites queries. |
| `DARKSKYSITES_TIMEOUT_SECONDS` | `float` | `10.0` | No | Timeout in seconds for upstream DarkSkySites HTTP requests. Timed out calls return an unavailable status result gracefully. |
| `DARKSKYSITES_CACHE_TTL_SECONDS` | `int` | `86400` | No | Duration in seconds (default: 24 hours) to cache DarkSkySites SQM readings in memory. |
| `ENABLE_API_DOCS` | `bool` | `true` | No | Controls exposure of interactive OpenAPI docs (`/docs` and `/redoc`). Set to `false`, `0`, or `no` in production to prevent schema exploration. |
| `CORS_ALLOWED_ORIGINS` | `str` | `""` | No | Comma-separated list of allowed HTTP origins (e.g. `https://app.example.com,https://staging.example.com`). If empty or unset, CORS middleware is disabled and cross-origin browser requests are rejected. |

---

## Health Check and Readiness Probes

The backend exposes three health check endpoints for load balancers and container orchestrators:

| Endpoint | Method | Success Code | Purpose & Logic | Verification Command (PowerShell) |
|---|---|---|---|---|
| `/` | `GET` | `200 OK` | Root liveness check returning `{"status": "ok"}`. | `Invoke-RestMethod -Uri http://127.0.0.1:8001/` |
| `/health` | `GET` | `200 OK` | Standard orchestrator liveness probe returning `{"status": "ok"}` without database overhead. | `Invoke-RestMethod -Uri http://127.0.0.1:8001/health` |
| `/health/db` | `GET` | `200 OK` | Deep readiness probe executing `SELECT 1` on PostgreSQL. Returns `200` with `{"status": "ok", "database": "connected"}` if healthy; returns `503 Service Unavailable` on database error. | `Invoke-RestMethod -Uri http://127.0.0.1:8001/health/db` |

---

## Interactive API Documentation

When `ENABLE_API_DOCS=true` (the default setting for development):
- **Swagger UI**: [http://127.0.0.1:8001/docs](http://127.0.0.1:8001/docs)
- **ReDoc UI**: [http://127.0.0.1:8001/redoc](http://127.0.0.1:8001/redoc)
- **OpenAPI JSON**: [http://127.0.0.1:8001/openapi.json](http://127.0.0.1:8001/openapi.json)

To disable in staging or production environments, set `ENABLE_API_DOCS=false` in `.env`.

---

## Running the Test Suite

AstroOS includes a comprehensive test suite covering database operations, astronomy adapters, weather resilience, and production readiness.

Run the test suite using the virtual environment's Python interpreter:
```powershell
# Full test suite (verified baseline: 320 passed, 3 warnings)
.\venv\Scripts\python.exe -m pytest -q

# Run production-readiness regression tests
.\venv\Scripts\python.exe -m pytest tests/test_production_readiness.py -v --tb=short

# Run database-readiness tests
.\venv\Scripts\python.exe -m pytest tests/test_database_readiness.py -v --tb=short
```

---

## Database Migrations (Alembic)

Database schema migrations are managed using Alembic.

```powershell
# Check current migration revision
.\venv\Scripts\alembic.exe current

# Apply pending migrations
.\venv\Scripts\alembic.exe upgrade head

# Generate a new migration after modifying models in app/models/
.\venv\Scripts\alembic.exe revision --autogenerate -m "describe changes"
```
> [!CAUTION]
> Never execute `alembic downgrade` on a production database without a verified snapshot/backup and an approved rollback strategy.

---

## Production Deployment Considerations

Before deploying AstroOS Backend to an internet-facing or shared environment:

1. **Authentication & Authorization**: The current backend version does not include user authentication or role-based access control. Endpoints must be protected by an authentication gateway, proxy, or identity middleware before public exposure.
2. **CORS Restrictions**: Explicitly configure `CORS_ALLOWED_ORIGINS` in `.env` to include only verified frontend domains (e.g. `https://astros.example.com`). Avoid using wildcard origins (`*`) in production.
3. **Disable API Documentation**: Set `ENABLE_API_DOCS=false` to prevent unwanted introspection of API schemas and parameters.
4. **Reverse Proxy & Process Management**:
   - Run Uvicorn behind a hardened reverse proxy (e.g., Nginx, Traefik, AWS ALB) for TLS termination, request buffering, and rate limiting.
   - Run multiple Uvicorn worker processes via Gunicorn or container orchestrators (Docker, Kubernetes, ECS) with a health probe pointing to `/health` (liveness) and `/health/db` (readiness).
5. **Secrets & Credentials Management**: Store `DATABASE_URL` and `DARKSKYSITES_API_KEY` in environment secrets or dedicated secret vaults (e.g., AWS Secrets Manager, HashiCorp Vault). Never commit `.env` to version control.
6. **Disclaimer**: These deployment and configuration instructions provide general best-practice operational guidance and do not constitute formal security certification, compliance sign-off, or penetration testing validation.
