# ITAM Platform — Enterprise IT Asset Management

A multi-tenant, cloud-native SaaS platform for managing the complete lifecycle of IT
assets — from purchase request to disposal — built for organizations running
thousands to hundreds of thousands of assets.

**Stack:** Node.js 22 · TypeScript (strict) · NestJS · TypeORM · PostgreSQL · JWT · OpenAPI

## Feature highlights

| Domain | Capabilities |
| --- | --- |
| **Multi-tenancy** | Shared-schema tenant isolation enforced on every query; per-tenant branding, settings, roles |
| **Assets** | Full inventory record (hardware specs, location, financials, custom fields per category), lifecycle state machine (Planning → … → Disposal), immutable per-asset history |
| **Labels** | Auto-generated sequential asset tags, QR code + Code-128 barcode PNGs, scan-to-resolve endpoint |
| **Check-in/out** | Assignments with digital signatures, photos, expected return dates, damage notes, automatic overdue alerts |
| **Licenses** | Seat pools, device/user seat consumption, expiry & renewal alerts, keys never exposed in lists/exports |
| **Maintenance** | Preventive/corrective/vendor work orders with costs, parts, scheduling |
| **Warranty** | 90/60/30/7-day expiry alert windows (per-tenant configurable), daily sweep |
| **Inventory audits** | Scan-driven physical audits; computes missing / moved / unknown automatically |
| **Dashboards** | Totals, status/category/branch/department breakdowns, purchase cost, straight-line depreciation, recent activity |
| **Reports** | Asset inventory, warranty, maintenance, assignments, licenses, financial — as CSV, XLSX, PDF or JSON |
| **Security** | RBAC with 8 seeded system roles + custom roles, permission matrix, JWT access + rotating refresh tokens, bcrypt, rate limiting, helmet, strict validation, append-only audit log of every mutation |

## Quick start

```bash
# 1. Full stack with PostgreSQL
docker compose up --build

# 2. Or local dev against the in-memory database (no services needed)
npm install
DB_TYPE=sqljs npm run start:dev
```

Interactive API documentation: **http://localhost:3000/api/v1/docs**

Create your first tenant:

```bash
curl -X POST http://localhost:3000/api/v1/auth/register-organization \
  -H 'Content-Type: application/json' \
  -d '{
    "organizationName": "Acme Corporation",
    "organizationSlug": "acme",
    "adminEmail": "admin@acme.com",
    "adminFullName": "Jane Admin",
    "adminPassword": "Str0ng!Passphrase"
  }'
```

Then call the API with the returned `accessToken` as a Bearer token. Demo data:
`DB_TYPE=sqljs npm run seed` (or against your Postgres instance).

## Tests

```bash
npm run typecheck   # strict TypeScript
npm test            # unit tests (lifecycle state machine, …)
npm run test:e2e    # boots the whole platform in-memory and walks every module
```

The e2e suite covers tenant registration, login/refresh-rotation/logout, RBAC
enforcement, asset lifecycle rules, check-out/in, license seats, maintenance,
inventory audit reconciliation, dashboards, all report formats, audit logging
and cross-tenant isolation.

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — layers, multi-tenancy model, security design, data model, scalability path, roadmap

## Repository layout

```
src/
  common/          # base entities, guards, decorators, pagination, generic tenant CRUD
  config/          # typed 12-factor configuration
  database/        # TypeORM wiring (PostgreSQL / in-memory)
  modules/
    auth/          # tenant registration, JWT login, refresh rotation
    organizations/ users/ branches/ departments/ employees/ suppliers/
    categories/    # asset types with custom field definitions
    assets/        # inventory, lifecycle state machine, QR/barcode, history
    assignments/   # check-in / check-out
    licenses/      # software licenses + seats
    maintenance/   # work orders
    inventory-audits/
    notifications/ # in-app inbox + scheduled warranty/license/overdue sweeps
    audit-log/     # append-only audit trail (global interceptor)
    dashboard/ reports/
  seeds/           # demo data
test/              # full-platform e2e suite
```
