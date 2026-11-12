# SentinelOps

**Intelligent Self-Healing CI/CD and Deployment Monitoring Platform**

SentinelOps is made of two independent Flask applications plus MySQL, all started with one Docker Compose command:

| Component | Purpose | URL |
|---|---|---|
| **SentinelOps Dashboard** | Deployment monitoring UI + REST API for Jenkins | http://localhost:5000 |
| **Demo Application** | The workload being deployed (health/version/failure simulation) | http://localhost:8080 |
| **MySQL 8.0** | Persistent storage (Docker volume `sentinelops_mysql_data`) | localhost:3307 |

> Phase 1 (this repo): local platform, database, migrations, dashboard, API, tests.
> Phase 2 (next): Jenkins pipeline and AWS deployment.

---

## Features

**Dashboard**
- Registration / login (hashed passwords, CSRF-protected forms, safe redirects)
- KPIs: total, successful, failed, rolled-back deployments, success percentage
- Chart.js analytics: 14-day stacked trend, status doughnut, per-service breakdown (auto-refresh every 60 s)
- Deployment history with search, filters and pagination; deployment details page with service timeline
- Services CRUD with per-service stats and **on-demand health checks** (calls the service's `health_check_url`)
- Incidents CRUD with severity / status, resolve action and filters
- **Self-healing signals:** a `failed` / `rolled_back` deployment automatically opens an incident and marks the service `degraded`; the next `success` marks it `active` again
- Dark, responsive DevOps theme (Bootstrap 5, mobile offcanvas sidebar)

**Demo application**
- `GET /` · `GET /health` · `GET /version`
- `BREAK=true` makes `/` and `/health` return HTTP 500 (simulated broken release); `/version` keeps working

---

## Project structure

```
sentinelops/
├── dashboard/
│   ├── app/
│   │   ├── __init__.py          # application factory
│   │   ├── extensions.py        # db, migrate, login manager, CSRF
│   │   ├── models.py            # User, Service, Deployment, Incident
│   │   ├── deployments.py       # record deployment + auto-incident logic
│   │   ├── stats.py             # KPI + chart aggregations
│   │   ├── health.py            # remote health checks
│   │   ├── validators.py        # form / API validation
│   │   ├── seed.py              # bootstrap admin + demo data
│   │   ├── cli.py               # flask create-admin / seed-demo / simulate-deployment
│   │   ├── errors.py            # JSON errors for /api, HTML pages elsewhere
│   │   ├── template_helpers.py  # Jinja filters
│   │   ├── routes/              # auth, main, services, incidents, api blueprints
│   │   ├── templates/           # Jinja templates
│   │   └── static/              # css/style.css, js/app.js, js/dashboard.js
│   ├── migrations/              # Flask-Migrate (Alembic) — 0001_initial_schema
│   ├── tests/                   # pytest (SQLite in-memory)
│   ├── boot.py                  # container entrypoint: wait for DB → migrate → seed → gunicorn
│   ├── config.py · wsgi.py
│   ├── Dockerfile · requirements.txt
├── demo-app/
│   ├── app.py · tests/ · Dockerfile · requirements.txt
├── docker-compose.yml
├── .env.example · .gitignore · .gitattributes
└── README.md
```

---

## Quick start — Windows (CMD + Docker Desktop)

Prerequisites: **Docker Desktop** running (WSL 2 backend recommended).

```cmd
cd C:\path\to\sentinelops

:: 1. Create your environment file
copy .env.example .env

:: 2. Edit secrets (replace every "change-me" value)
notepad .env

:: 3. Build and start everything
docker compose up --build
```

First start takes ~1 minute: MySQL initialises, then the dashboard waits for it, applies migrations, creates the admin user and loads demo data.

Open:
- Dashboard → http://localhost:5000 (sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD` from `.env`, or register a new account)
- Demo app → http://localhost:8080/health

Run in the background instead:

```cmd
docker compose up --build -d
docker compose ps
docker compose logs -f dashboard
```

Stop / reset:

```cmd
:: stop containers (data kept)
docker compose down

:: stop AND delete the MySQL volume (full reset)
docker compose down -v
```

> **Tip:** generate a secret with `python -c "import secrets; print(secrets.token_hex(32))"`.
> Avoid `$` in `.env` values (Compose treats it as a variable); if you need one, write `$$`.
> If port 5000, 8080 or 3307 is already in use, change `DASHBOARD_PORT`, `DEMO_APP_PORT` or `MYSQL_HOST_PORT` in `.env`.

### Linux / macOS

```bash
cp .env.example .env   # then edit it
docker compose up --build
```

---

## REST API (for Jenkins)

Authenticate with the `SENTINELOPS_API_KEY` value, either as `X-API-Key: <key>` or `Authorization: Bearer <key>`. GET endpoints also work from a logged-in browser session.

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | Liveness + DB check (no auth) |
| GET | `/api/stats` | Deployment KPIs |
| GET | `/api/deployments` | List — `?limit=50&offset=0&status=failed&service_name=demo-app` |
| GET | `/api/deployments/<id>` | Single deployment with linked incidents |
| POST | `/api/deployments` | Record a deployment |
| GET | `/api/services` | List services |

### POST /api/deployments

Required fields: `commit_id`, `commit_author`, `commit_message`, `build_number`, `image_tag`, `deployment_status`, `service_name`.
Optional: `environment` (`development` / `staging` / `production`, default `production`), `duration_seconds`, `triggered_by`, `notes`.

`deployment_status`: `success`, `failed`, `rolled_back`, `in_progress` (aliases such as `passed`, `failure`, `rollback`, `running` are accepted).
Unknown `service_name` values are auto-registered as new services.

Responses: `201` created · `400` invalid JSON · `401` bad/missing key · `422` validation errors (per-field messages) · `503` API key not configured on server.

**Windows CMD example** (replace `YOUR_API_KEY`):

```cmd
curl -X POST http://localhost:5000/api/deployments ^
  -H "Content-Type: application/json" ^
  -H "X-API-Key: YOUR_API_KEY" ^
  -d "{\"commit_id\":\"a1b2c3d4e5f6\",\"commit_author\":\"Jenkins\",\"commit_message\":\"Release 1.1\",\"build_number\":101,\"image_tag\":\"sentinelops/demo-app:101\",\"deployment_status\":\"success\",\"service_name\":\"demo-app\"}"

curl -H "X-API-Key: YOUR_API_KEY" http://localhost:5000/api/stats
curl -H "X-API-Key: YOUR_API_KEY" "http://localhost:5000/api/deployments?limit=5"
```

**PowerShell example:**

```powershell
$body = @{ commit_id="a1b2c3d4e5f6"; commit_author="Jenkins"; commit_message="Release 1.1";
           build_number=102; image_tag="sentinelops/demo-app:102";
           deployment_status="failed"; service_name="demo-app" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:5000/api/deployments `
  -Headers @{ "X-API-Key" = "YOUR_API_KEY" } -ContentType "application/json" -Body $body
```

Example `201` response:

```json
{
  "message": "Deployment recorded.",
  "deployment": { "id": 51, "service_name": "demo-app", "deployment_status": "failed", "build_number": 102, "...": "..." },
  "service_created": false,
  "incident_id": 9,
  "dashboard_url": "http://localhost:5000/deployments/51"
}
```

---

## Simulating failures with the demo app

```cmd
:: 1. In .env set BREAK=true, then recreate only the demo app
docker compose up -d --force-recreate demo-app

:: 2. Health check now fails with HTTP 500
curl -i http://localhost:8080/health

:: 3. In the dashboard: Services → demo-app → "Run health check" → UNHEALTHY

:: 4. Set BREAK=false again and recreate to "heal"
docker compose up -d --force-recreate demo-app
```

Record a deployment without curl, from inside the container:

```cmd
docker compose exec dashboard flask simulate-deployment --service demo-app --status failed
docker compose exec dashboard flask simulate-deployment --service demo-app --status success
```

---

## Database & migrations

Tables: `users`, `services`, `deployments`, `incidents` (+ `alembic_version`). Migrations run automatically on container start (`boot.py`). Manual commands:

```cmd
docker compose exec dashboard flask db current
docker compose exec dashboard flask db upgrade

:: after changing models.py
docker compose exec dashboard flask db migrate -m "describe change"
docker compose exec dashboard flask db upgrade
```

Other CLI commands:

```cmd
docker compose exec dashboard flask create-admin
docker compose exec dashboard flask seed-demo --force

:: open a MySQL shell (password = MYSQL_PASSWORD from .env)
docker compose exec mysql mysql -u sentinel -p sentinelops
```

---

## Running the tests

Inside the containers (no local Python needed):

```cmd
docker compose exec dashboard python -m pytest -v
docker compose exec demo-app python -m pytest -v
```

Or locally (Python 3.11+):

```cmd
cd dashboard
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m pytest -v

cd ..\demo-app
pip install -r requirements.txt
python -m pytest -v
```

Dashboard tests use an in-memory SQLite database, so MySQL is not required to run them. Coverage: auth, API auth/validation/filters/stats, auto-incident + self-healing logic, services & incidents CRUD, health checks (mocked), seeding and every UI page. Demo-app tests cover all endpoints and `BREAK` handling.

---

## Configuration reference (`.env`)

| Variable | Purpose |
|---|---|
| `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD` | **Required.** MySQL credentials |
| `MYSQL_DATABASE`, `MYSQL_USER` | DB name / app user |
| `SECRET_KEY` | **Required.** Flask session signing key |
| `SENTINELOPS_API_KEY` | **Required.** Key Jenkins sends to the API |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Optional bootstrap admin (created once) |
| `SEED_DEMO_DATA` | `true` loads sample data on first start (only if DB is empty) |
| `DASHBOARD_PORT`, `DEMO_APP_PORT`, `MYSQL_HOST_PORT` | Host ports |
| `APP_VERSION`, `BUILD_NUMBER`, `COMMIT_ID` | Reported by demo app `/version` |
| `BREAK` | `true` = demo app health check fails |
| `LOG_LEVEL`, `GUNICORN_WORKERS` | Runtime tuning |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `required variable MYSQL_PASSWORD is missing` | You haven't created `.env` — run `copy .env.example .env` |
| Dashboard logs `Database not ready` for a while | Normal on first boot; MySQL initialisation can take 30–60 s |
| `Access denied for user` after changing passwords | The volume keeps the old credentials — run `docker compose down -v` then start again |
| `port is already allocated` | Change the port variables in `.env` |
| Charts don't appear | The browser needs internet access to load Bootstrap/Chart.js from the jsDelivr CDN |

---

## Next phase (not implemented yet)

- Jenkinsfile: test → build image → deploy → health-check → `POST /api/deployments`
- Automatic rollback when the demo app's `/health` fails after deploy
- AWS deployment (EC2 / ECR)
