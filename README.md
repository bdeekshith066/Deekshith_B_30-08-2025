
# Loop Store Monitor — Take-Home Project

## 📌 Project Overview
This project implements a backend system to **monitor store uptime/downtime** based on periodic pings.  
Restaurant owners can generate reports showing how often their stores were online or offline **during business hours** in the last **hour, day, and week**.

It is built with **FastAPI**, **SQLAlchemy (async)**, and supports both **SQLite (default)** and **Postgres**.

---

## 🚀 Features
- **CSV Ingestion**: Loads ping logs, business hours, and timezones into the database.
- **Uptime/Downtime Reports**:
  - Uptime/downtime **last hour** (minutes)
  - Uptime/downtime **last day** (hours)
  - Uptime/downtime **last week** (hours)
- **Trigger + Poll API**:
  - `POST /trigger_report` → starts background computation, returns `report_id`.
  - `GET /get_report?report_id=...` → returns `"Running"`, `"Failed"`, or streams the finished CSV.
- **Time-zone aware** (handles local business hours, overnight shifts, DST).
- **Safe defaults**:
  - Missing business hours → 24×7 open
  - Missing timezone → America/Chicago
  - No pings → assume inactive

---

## 🗂️ Project Structure
```

app/
api/         → API endpoints (health, report)
services/    → Report computation logic
utils/       → Time window & status segment utilities
models.py    → SQLAlchemy ORM models
db.py        → Async DB setup + session provider
config.py    → Environment settings (via pydantic-settings)
ingest.py    → Loads CSV data into DB
main.py      → FastAPI app entrypoint
tests/         → Unit and integration tests
reports/       → Generated CSV reports

````

---

## ⚙️ Setup & Installation
```bash
# 1. Clone repo & install requirements
git clone https://github.com/bdeekshith066/Deekshith_30-08-2025.git
pip install -r requirements.txt

# 2. Configure .env (SQLite default)
cat <<EOF > .env
DATABASE_URL=sqlite+aiosqlite:///./store_monitor.sqlite
STATUS_CSV=./data/store_status.csv
HOURS_CSV=./data/business_hours.csv
TZ_CSV=./data/store_timezone.csv
EOF

# (Optional) For Postgres instead (requires docker-compose up -d):
# DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/store_monitor

# 3. Ingest data
python -m app.ingest

# 4. Run API
uvicorn app.main:app --reload
````

---

## 📡 API Endpoints

### Health

```bash
GET /healthz       → {"ok": true} if DB is reachable
GET /debug/tables  → lists DB tables
```

### Report Flow

#### 1. Trigger report

```bash
curl -X POST http://127.0.0.1:8000/trigger_report
# {"report_id": "abcd1234..."}
```

#### 2. Poll for result

```bash
curl "http://127.0.0.1:8000/get_report?report_id=abcd1234..."
# → "Running" | "Failed" | CSV file
```

---

## 📊 Sample CSV Output

Schema:

```
store_id,
uptime_last_hour(in minutes),
uptime_last_day(in hours),
uptime_last_week(in hours),
downtime_last_hour(in minutes),
downtime_last_day(in hours),
downtime_last_week(in hours)
```

Example row:

```
00017c6a...,60.0,8.53,58.77,0.0,1.97,16.73
```

---

## ✅ Testing

```bash
pytest
```

Integration test (`test_api.py`) runs the trigger → poll → CSV download flow against a running server.

---

## 🧩 Design Choices

* **Async Database (SQLAlchemy + async):** Non-blocking for scalability.
* **Trigger + Poll Workflow:** Background job avoids request timeouts.
* **Safe Defaults:** Graceful handling of missing hours/timezones/pings.
* **CSV Output:** Portable and BI-tool friendly.

---

## 🔮 Improvements

* Switch to Postgres + Alembic migrations for production.
* Use Celery/Redis for distributed background jobs.
* Add caching/pre-aggregation for faster repeated reports.
* Improve observability with logging & metrics.
* Add auth & RBAC for customer-facing use.
