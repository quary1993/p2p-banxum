# Local Development Runbook

## Initial Setup

```bash
make setup
```

## Start The Local Stack

```bash
make up
```

Services:

- Backend API: `http://localhost:8000`
- Backend health: `http://localhost:8000/api/v1/health/`
- API docs: `http://localhost:8000/api/docs/`
- Frontend: `http://localhost:5173`
- Mailpit: `http://localhost:8025`
- MinIO console: `http://localhost:9001`

## Run Without Docker

```bash
make migrate
make backend-run
make frontend-run
```

`make up` runs backend migrations before starting the backend container. When running without Docker, run `make migrate` yourself before `make backend-run`.

If an old local SQLite database was created before the custom accounts user model existed, delete `db.sqlite3` and rerun `make migrate`. This does not affect PostgreSQL-backed staging or production databases.

## Handoff Checks

```bash
make agent-check
```
