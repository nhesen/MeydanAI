# MeydanAI

MeydanAI is a mobile-first football analytics platform foundation. This
repository currently contains the Prompt 1 baseline; product domains and
AI/CV processing will be added in later phases.

## Architecture

```text
Browser
  -> Next.js App Router (frontend/)
  -> FastAPI REST API (backend/)
  -> SQLAlchemy
  -> PostgreSQL

Future video processing:
FastAPI -> asynchronous Python AI/CV workers (not implemented yet)
```

- **Frontend:** Next.js App Router, TypeScript strict mode, Tailwind CSS
- **Backend:** Python 3.12+, FastAPI, Pydantic
- **Persistence:** PostgreSQL, SQLAlchemy 2, Alembic
- **Local infrastructure:** Docker Compose

Backend modules follow package-by-feature. Cross-cutting configuration,
database setup and error handling live under `app/core`; transport schemas live
under `app/schemas`; versioned routes live under `app/api`. Product packages
such as `matches`, `teams`, `players`, `analytics`, `highlights`, `auth` and
`admin` will be created only when their features are implemented.

The frontend keeps route composition in `app`, shared UI in `components`,
domain behavior in `features`, HTTP access in `services`, runtime helpers in
`lib` and transport contracts in `types`.

## Prerequisites

- Node.js 20.9 or newer and npm
- Python 3.12 or newer
- Docker Desktop with Docker Compose

## Local setup

1. Create local environment files:

   ```powershell
   Copy-Item .env.example .env
   Copy-Item backend/.env.example backend/.env
   Copy-Item frontend/.env.example frontend/.env.local
   ```

2. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   docker compose ps
   ```

3. Set up and migrate the backend:

   ```powershell
   Set-Location backend
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

4. Start the frontend in a second terminal:

   ```powershell
   Set-Location frontend
   npm install
   npm run dev
   ```

Open `http://localhost:3000`. The API health contract is available at
`http://localhost:8000/api/v1/health`.

## Configuration

Frontend requires `NEXT_PUBLIC_API_BASE_URL`, the public absolute URL of the
backend API.

Backend settings:

- `APP_ENV`: `development`, `test` or `production`.
- `APP_NAME`: service name exposed in OpenAPI.
- `API_V1_PREFIX`: versioned API prefix; defaults to `/api/v1`.
- `DATABASE_URL`: required PostgreSQL SQLAlchemy URL using the psycopg driver.
- `CORS_ALLOWED_ORIGINS`: required comma-separated trusted frontend origins.

Production has no database or CORS fallback. Never commit real credentials;
use the deployment platform's secret manager.

## Database and migrations

Alembic is the only schema owner. Migrations are stored in
`backend/alembic/versions`. Apply them with:

```powershell
Set-Location backend
alembic upgrade head
```

Create future revisions only after importing the relevant SQLAlchemy models
into Alembic metadata:

```powershell
alembic revision --autogenerate -m "describe change"
```

To reset only the local database:

```powershell
docker compose down -v
docker compose up -d postgres
```

This deletes local PostgreSQL data and must not be used against shared or
production environments.

## Quality commands

Frontend:

```powershell
Set-Location frontend
npm run lint
npm run typecheck
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"
npm run build
```

Backend:

```powershell
Set-Location backend
ruff check .
ruff format --check .
mypy app
pytest
alembic upgrade head --sql
```

Backend tests use FastAPI's in-process test client and do not make external
network or database requests. The Alembic offline command validates migration
generation without connecting to PostgreSQL. Migrations must additionally be
applied against the local Compose database before release.

## API conventions

- Versioned product endpoints use `/api/v1`.
- Successful responses use `{ "data": ..., "timestamp": ... }`.
- Errors use RFC 7807 `application/problem+json` and include a stable
  `errorCode`. Validation errors may include a field-level `errors` object.
- Sensitive exception details and stack traces are never returned to clients.

## Current limitations

- Authentication, roles and domain APIs are intentionally not implemented.
- Match, team, player and analytics database models belong to Prompt 3.
- The current UI is a minimal foundation health screen, not the Prompt 2
  redesign.
- Background jobs, OpenCV and computer-vision models are intentionally absent.
