# Architecture

```text
React + TypeScript
        ↓
FastAPI REST API
        ↓
SQLAlchemy
        ↓
PostgreSQL
```

## Foundation

The repository separates a React/TypeScript frontend from a Python/FastAPI backend. Vite serves and builds the frontend; Tailwind CSS provides styling. React Router owns routes and TanStack Query is installed through a shared provider for future server state. Zustand is installed for future client state; no artificial store is created before a real requirement exists.

Frontend `src/app` owns application composition, `src/pages` holds the temporary home screen, and `src/test` contains test setup. Future feature modules can live in `src/features`, with shared code extracted only when needed.

The backend separates API routes, core settings, and database infrastructure under `app`. Pydantic Settings reads the root `.env` and environment variables. SQLAlchemy uses the synchronous psycopg driver and a session dependency with scoped cleanup. Alembic is configured against empty shared metadata; no domain tables or migrations exist yet. DATABASE_URL is optional until database operations are used. Database connections are lazy, so application startup and `/health` do not require PostgreSQL. Health is a liveness endpoint, not a database readiness check.

PostgreSQL is the intended relational database. Installation, domain design and schema migrations are deferred to the next milestone. DATABASE_URL is optional for startup and must be set before database operations. Frontend and backend run locally as separate processes. Explicit local CORS origins permit the Vite frontend to access the API. Settings and credentials remain server-side; any future Vite `VITE_` variables are public and must never contain secrets.

## Future integrations (not implemented)

Stripe TEST mode will support payments. Maps/geocoding, image storage, and transactional email providers will be selected later. Integrations will be placed behind backend service boundaries where appropriate. No vendor SDKs or fake implementations are included now.

## Planned backend organisation

`app/api` holds HTTP routes, `app/core` configuration and `app/db` database infrastructure. Future `models`, `schemas`, `services` and `security` packages will separate relational entities, request/response validation, business rules and authentication/authorisation when those responsibilities exist. No empty abstraction layers or domain entities are needed now. Session cleanup is provided; future business operations must define explicit transaction boundaries. Startup never creates tables.
