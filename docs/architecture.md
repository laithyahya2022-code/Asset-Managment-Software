# Architecture

This document explains the design decisions behind the ITAM platform and the
path from the current codebase to very large deployments.

## 1. Shape of the system

The platform is a modular monolith exposing a versioned REST API
(`/api/v1`, OpenAPI at `/api/v1/docs`). A modular monolith is the right
starting point for an enterprise product: one deployable, one transaction
boundary, strict module seams (NestJS modules with explicit imports/exports)
that allow extraction into services later if scale demands it.

```
Presentation   controllers, DTO validation, OpenAPI
Application    module services (use cases, transactions)
Domain         entities, lifecycle state machine, permission catalog
Infrastructure TypeORM repositories, schedulers, exporters, label generation
Cross-cutting  auth guards, RBAC guard, audit interceptor, exception filter,
               rate limiter, configuration
```

Key seams and where they live:

| Concern | Location |
| --- | --- |
| Tenant isolation | `common/entities/tenant-base.entity.ts` + `common/services/tenant-crud.service.ts` |
| Permission catalog & system roles | `common/security/permissions.ts` |
| Lifecycle state machine | `modules/assets/asset-lifecycle.ts` |
| Audit trail | `modules/audit-log/` (global interceptor + injectable service) |
| Background jobs | `modules/notifications/alerts.scheduler.ts` |
| Report rendering | `modules/reports/export.service.ts` (CSV/XLSX/PDF/JSON behind one interface) |

## 2. Multi-tenancy

**Model: shared database, shared schema, tenant discriminator column.**

- Every tenant-scoped table extends `TenantBaseEntity`, which carries an
  indexed `organizationId`.
- The JWT carries the tenant id; services receive it explicitly as the first
  argument of every method. There is no ambient/global tenant state, which
  keeps the code testable and makes cross-tenant access impossible to write
  accidentally: a foreign UUID simply resolves to 404 inside the caller's
  tenant (covered by e2e tests).
- Uniqueness is always tenant-scoped composite (`organizationId + assetTag`,
  `organizationId + email`, …), so tenants never contend over identifiers.

Why shared-schema? It has the lowest operational cost per tenant and scales
to thousands of tenants. The seams are in place to move hot tenants to
dedicated databases later (row-level security or schema-per-tenant) because
tenancy is explicit in every query.

## 3. Security

- **AuthN** — short-lived JWT access tokens (15 min) + long-lived refresh
  tokens with **rotation**: only the SHA-256 digest of the latest refresh
  token is stored; refresh re-issues and revokes the previous one, logout and
  password change revoke globally. Passwords use bcrypt (configurable cost).
- **AuthZ** — RBAC with a `resource:action` permission catalog. Eight system
  roles are seeded per tenant (Org Admin → Read-Only); tenants compose custom
  roles from the same catalog. A global `PermissionsGuard` enforces
  `@RequirePermissions()` declarations on every route.
- **Guard order**: rate limiter → JWT auth → permissions.
- **Input** — global `ValidationPipe` with `whitelist` + `forbidNonWhitelisted`
  (unknown fields are rejected, not ignored); DTOs validate types, lengths,
  UUIDs, IP/MAC formats, enum membership; asset custom fields are validated
  against their category's definitions.
- **Output** — `ClassSerializerInterceptor` strips `@Exclude()`d secrets
  (password/refresh hashes); license keys are omitted from list views and
  exports; audit metadata redacts password/token/signature/key fields.
- **Transport/headers** — helmet, configurable CORS, HTTPS expected at the
  load balancer.
- **SQLi** — parameterized queries only (TypeORM repositories/query builder).
- **Audit** — a global interceptor records every successful mutation
  (actor, tenant, entity, redacted payload); domain services add
  business-level entries (logins, lifecycle changes, check-in/out). The log
  is append-only.

## 4. Data model (core)

```
organizations 1─* users *─1 roles
organizations 1─* branches 1─* departments 1─* employees
organizations 1─* asset_categories 1─* assets
assets 1─* asset_events            (immutable history)
assets 1─* asset_assignments *─1 employees   (check-in/out cycles)
assets 1─* maintenance_records *─1 suppliers
software_licenses 1─* license_assignments (→ asset and/or employee)
inventory_audits 1─* inventory_audit_scans
audit_logs, notifications          (per tenant / per user)
```

Conventions: UUID keys, `createdAt/updatedAt/deletedAt` (soft deletes)
everywhere, composite indexes on every `organizationId + hot column`
(status, category, branch, warranty end, tag), decimal money columns,
`simple-json` documents for custom fields/attachments/results.

**Migrations** — development uses `DB_SYNCHRONIZE=true`; production must use
TypeORM migrations (`typeorm migration:generate` against the entity set).
Entities are written engine-portable so the e2e suite can run the entire
platform on an in-memory database in CI.

## 5. Asset lifecycle

`asset-lifecycle.ts` encodes the full chain
Planning → Purchase Request → Approval → Procurement → Receiving → Inventory →
Deployment → Assignment ⇄ Maintenance/Repair/Transfer → Retirement → Disposal
as an explicit transition map. Illegal jumps are rejected at the service
layer; `ASSIGNED` can only be entered/left through check-out/check-in so the
assignment ledger and asset state can never diverge (both are updated in one
transaction, with a pessimistic row lock on PostgreSQL).

## 6. Performance & scalability

Current mechanics:

- Pagination everywhere (`page/pageSize` capped at 200), sortable columns
  whitelisted.
- Filtered search via query builder with tenant-first composite indexes.
- Grouped dashboard counts computed in SQL; parallelized with `Promise.all`.
- Report row caps (50k) to bound memory; exports stream from buffers.
- Stateless API → horizontal scaling behind a load balancer is trivial
  (JWTs carry all request context).

Scale-up path (documented intentionally, not speculatively built):

1. **Read replicas** for dashboards/reports (TypeORM replication config).
2. **Redis** — cache dashboard aggregates, move rate limiting from
   in-memory to shared storage, host BullMQ queues.
3. **Background workers** — move report generation and alert sweeps to a
   dedicated worker process (the scheduler module is already isolated).
4. **Search** — mirror assets into OpenSearch/Meilisearch when LIKE-based
   search stops being enough (search is already behind one service method).
5. **Object storage** — attachments/photos/signatures store URLs today;
   add pre-signed S3/Azure Blob upload endpoints.

## 7. Extension roadmap

| Planned capability | Prepared seam |
| --- | --- |
| SSO (Entra ID, Google, LDAP) | `AuthModule` issues its own JWTs; add passport strategies that resolve to the same principal |
| Email/Slack/Teams notifications | `NotificationsService.dispatch()` fan-out point |
| Approval chains (purchase requests) | lifecycle statuses `PURCHASE_REQUESTED/APPROVED` already modeled |
| Mobile app / integrations | same REST API; OpenAPI spec is generated |
| GraphQL | NestJS GraphQL module can wrap existing services |
| RFID/IoT | `assets/scan/:code` resolves any code carried by a tag |
| Scheduled reports | reports are pure functions of tenant + type; schedule with the existing cron infrastructure |

## 8. Testing strategy

- **Unit** — pure domain logic (state machine).
- **E2E** — the real application (all guards, interceptors, validation) boots
  against an in-memory database and is driven through HTTP for every module,
  including negative cases: RBAC denial, tenant isolation, illegal lifecycle
  transitions, seat exhaustion, rotation revocation.
- CI (GitHub Actions) runs typecheck, unit, e2e and build on every push.
