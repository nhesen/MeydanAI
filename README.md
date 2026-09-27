# MeydanAI

MeydanAI is a mobile-first football match platform. Organizers create matches,
players join through a QR token, and the product surfaces real match, player,
team, analytics, and highlight data from PostgreSQL. There is no fake production
analytics layer and no on-device computer-vision model in this repository.

## Architecture

```text
Browser
  -> Next.js App Router (frontend/)
  -> FastAPI /api/v1 (backend/)
  -> SQLAlchemy 2
  -> PostgreSQL 17
```

- **Frontend:** Next.js App Router, TypeScript, Tailwind CSS
- **Backend:** Python 3.12+, FastAPI, Pydantic Settings, Argon2id sessions
- **Persistence:** PostgreSQL, SQLAlchemy 2, Alembic
- **Local infrastructure:** Docker Compose for PostgreSQL, optional API and web images

Authentication uses opaque Bearer session tokens stored as SHA-256 hashes.
Match organizers can also use the legacy `X-Organizer-Token` capability token.
Public QR join, public match detail, and public directory/analytics endpoints
remain unauthenticated.

## Project structure

```text
frontend/     Next.js application
backend/      FastAPI application, Alembic migrations, pytest
compose.yaml  Local PostgreSQL plus optional API/web containers
```

## Prerequisites

- Node.js 20.9 or newer and npm
- Python 3.12 or newer
- Docker Desktop with Docker Compose, if you want a local PostgreSQL container

## Environment setup

```powershell
Copy-Item .env.example .env
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
```

Never commit `.env`, `.env.local`, tokens, or database passwords. The example
files document required variables without real secrets.

### Root `.env`

Used by Compose for the PostgreSQL container.

### Backend

- `APP_ENV`: `development`, `test`, or `production`
- `DATABASE_URL`: required PostgreSQL SQLAlchemy URL (`postgresql+psycopg://...`)
- `CORS_ALLOWED_ORIGINS`: comma-separated trusted frontend origins
- `AUTH_BOOTSTRAP_ADMIN_EMAIL`: optional first-admin bootstrap email
- `AUTH_RATE_LIMIT_ENABLED`: must remain `true` in production
- `INTERNAL_WORKER_TOKEN`: required only for internal ingestion endpoints

Production rejects wildcard CORS and disabled login/register rate limits.

### Frontend

- `NEXT_PUBLIC_API_URL`: public absolute backend URL
- `NEXT_PUBLIC_APP_URL`: public frontend URL encoded into join QR codes

## Local development

Recommended path: run PostgreSQL in Compose, then run the API and Next.js app
on the host.

1. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   docker compose ps
   ```

2. Install, migrate, and run the backend:

   ```powershell
   Set-Location backend
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -e ".[dev]"
   alembic upgrade head
   uvicorn app.main:app --reload
   ```

3. Start the frontend in a second terminal:

   ```powershell
   Set-Location frontend
   npm install
   npm run dev
   ```

Open `http://localhost:3000`. Health is `http://localhost:8000/api/v1/health`.

The API does not run Alembic automatically on startup. Apply migrations
explicitly before serving traffic.

## Optional full Compose stack

After the root `.env` exists:

```powershell
docker compose up -d postgres
docker compose run --rm backend alembic upgrade head
docker compose up -d
```

This is a local convenience stack, not a production orchestrator. Rebuild the
frontend image after changing `NEXT_PUBLIC_API_URL` or `NEXT_PUBLIC_APP_URL`.

## Database and migrations

Alembic is the only schema owner. Revisions live in `backend/alembic/versions`.

```powershell
Set-Location backend
alembic upgrade head
alembic upgrade head --sql
alembic downgrade -1
```

Create a new revision only after the relevant SQLAlchemy models are imported
into Alembic metadata:

```powershell
alembic revision --autogenerate -m "describe change"
```

Before applying migrations to a shared or production database, take a backup.
`docker compose down -v` deletes the local PostgreSQL volume and must not be
used against shared data.

## Quality commands

Frontend:

```powershell
Set-Location frontend
npm run lint
npm run typecheck
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
$env:NEXT_PUBLIC_APP_URL = "http://localhost:3000"
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

Backend tests use FastAPI's in-process client and in-memory SQLite. They do not
call external providers, email, object storage, or a live computer-vision
service.

## Product areas

- Account register, login, logout, and profile
- Match create, public match detail, organizer manage, QR join, jersey assignment
- Dashboard, matches, players, teams, analytics rankings, and highlights
- Processing job create/retry and local OpenCV motion worker
- Admin dashboard, users, matches, players, teams, jobs, and highlights

## API conventions

- Versioned product endpoints use `/api/v1`
- Successful responses use `{ "data": ..., "timestamp": ... }`
- Errors use RFC 7807 `application/problem+json` with a stable `errorCode`
- Clients never receive stack traces, SQL constraint names, or Python exceptions

Public endpoints stay public. Admin endpoints require an admin session.
Organizer write endpoints accept the match owner session, an admin session, or
the legacy organizer token.

## Deployment overview

1. Provision PostgreSQL and set a real `DATABASE_URL`
2. Set `APP_ENV=production`, explicit CORS origins, and `AUTH_RATE_LIMIT_ENABLED=true`
3. Back up the database
4. Run `alembic upgrade head` from a release job or one-off container
5. Start the API with Uvicorn or an equivalent ASGI server
6. Build the frontend with production `NEXT_PUBLIC_*` values and serve the
   Next.js standalone output

Do not enable wildcard CORS, disable rate limits, or rely on example passwords
in production.

## Known limitations

- Local video analysis uses OpenCV motion tracking, not a trained player/jersey model
- Detected tracks are mapped to assigned players by field side and activity, not OCR
- If a match has no jersey assignments, the worker creates temporary detected players from motion tracks
- Reported speed, distance, sprints, and rating are clamped to football-plausible bounds; they are estimates, not GPS
- Broadcast-quality CV, cloud storage, and email verification are not implemented
- Email verification, password reset, and outbound email are not implemented
- Object storage and CDN-backed highlight media are not implemented
- Rate limiting is in-process and is not shared across multiple API replicas
- The organizer capability token remains a transitional fallback beside sessions
- Settings is an empty product page by design
- Docker daemon and live PostgreSQL migration smoke tests depend on the local
  machine; this repository validates migrations offline with
  `alembic upgrade head --sql` when Docker is unavailable
