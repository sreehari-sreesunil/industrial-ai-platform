# Industrial AI Platform

A full-stack Industrial Asset Observability Platform built using FastAPI, PostgreSQL, React, and modern telemetry-driven architecture.

The platform enables organizations to register industrial assets, define telemetry schemas, ingest real-time and CSV telemetry data, validate measurements, and visualize operational performance through interactive dashboards.

---

## Features

### Authentication

* JWT-based authentication
* Secure password hashing
* Login and logout workflows
* Protected API endpoints
* Protected frontend routes

### Asset Registry

* Organizations
* Facilities
* Asset Types
* Assets

### Metric Management

* Dynamic metric definitions
* Asset-type-specific metrics
* Validation ranges
* Unit definitions
* Typed telemetry schemas

### Telemetry

* Manual telemetry ingestion
* Bulk CSV telemetry ingestion
* Historical telemetry storage
* Latest telemetry snapshots
* Statistical aggregation

### Dashboards

* Operational overview dashboard
* Asset observability console
* KPI visualization
* Historical telemetry charts
* Telemetry analytics workspace

---

## Architecture

### Backend

* FastAPI
* SQLAlchemy
* PostgreSQL
* Alembic
* JWT Authentication
* Pydantic

### Frontend

* React
* Vite
* React Router
* Axios
* Tailwind CSS
* Recharts
* Lucide Icons

### Database

Core entities:

* Users
* Organizations
* Facilities
* Asset Types
* Assets
* Metric Definitions
* Telemetry Records

---

## Database Model

Organization
→ Facility
→ Asset
→ Asset Type
→ Metric Definitions
→ Telemetry Records

Telemetry is stored as flexible JSON payloads while maintaining schema validation through metric definitions.

---

## Authentication Flow

User Login

↓

JWT Token Generation

↓

Token Stored in Browser

↓

Authorization Header Attached

↓

Protected API Access

---

## Telemetry Flow

Metric Definition Created

↓

Telemetry Ingested

↓

Validation Engine Executes

↓

Stored in PostgreSQL

↓

Dashboard APIs Query Data

↓

Frontend Visualizes Results

---

## CSV Upload Flow

CSV Upload

↓

CSV Parsing

↓

Validation Engine

↓

Database Insert

↓

Success / Error Report

↓

Dashboard Refresh

---

## API Modules

### Authentication

* POST /auth/register
* POST /auth/login

### Organizations

* GET /organizations
* POST /organizations

### Facilities

* GET /facilities
* POST /facilities

### Asset Types

* GET /asset-types
* POST /asset-types

### Assets

* GET /assets
* POST /assets

### Metric Definitions

* GET /metric-definitions
* POST /metric-definitions

### Telemetry

* POST /telemetry/ingest
* GET /telemetry/assets/{asset_id}
* GET /telemetry/assets/{asset_id}/latest
* GET /telemetry/assets/{asset_id}/stats

### CSV Upload

* POST /csv/telemetry-upload

### Dashboard

* GET /dashboard/overview

---

## Running The Project

### Backend

```bash
cd backend

poetry install

poetry run alembic upgrade head

poetry run uvicorn app.main:app --reload
```

Backend:

```text
http://localhost:8000
```

Swagger:

```text
http://localhost:8000/docs
```

### Frontend

```bash
cd frontend

npm install

npm run dev
```

Frontend:

```text
http://localhost:5173
```

---

## MVP Goals Achieved

* Metadata-driven architecture
* Industrial asset registry
* Telemetry ingestion pipeline
* Validation engine
* Historical telemetry storage
* Dashboard analytics
* CSV ingestion workflow
* JWT authentication
* Protected operational APIs
* Full-stack observability platform

---

## Future Enhancements

* Role-based access control
* Predictive maintenance models
* Anomaly detection
* Alerting engine
* Real-time streaming telemetry
* WebSocket updates
* Multi-tenancy
* Deployment automation

---

## Author

Industrial AI Platform MVP

Built as a full-stack industrial observability and telemetry management system.
