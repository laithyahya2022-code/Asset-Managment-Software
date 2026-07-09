import { ClassSerializerInterceptor, INestApplication, ValidationPipe } from '@nestjs/common';
import { Reflector } from '@nestjs/core';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { AppModule } from '../src/app.module';
import { HttpExceptionFilter } from '../src/common/filters/http-exception.filter';

/**
 * Full-platform end-to-end walk-through: tenant registration, RBAC,
 * org structure, asset lifecycle, check-in/out, licenses, maintenance,
 * inventory audit, dashboard, reports, audit logs and tenant isolation.
 */
describe('ITAM platform (e2e)', () => {
  let app: INestApplication;
  let http: any;
  let token: string;

  // Ids collected along the way
  let branchId: string;
  let departmentId: string;
  let categoryId: string;
  let employeeId: string;
  let assetId: string;
  let assetTag: string;
  let assignmentId: string;
  let licenseId: string;
  let maintenanceId: string;
  let auditId: string;

  const auth = () => ({ Authorization: `Bearer ${token}` });

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({ imports: [AppModule] }).compile();
    app = moduleRef.createNestApplication();
    app.setGlobalPrefix('api/v1');
    app.useGlobalPipes(
      new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }),
    );
    app.useGlobalInterceptors(new ClassSerializerInterceptor(app.get(Reflector)));
    app.useGlobalFilters(new HttpExceptionFilter());
    await app.init();
    http = app.getHttpServer();
  });

  afterAll(async () => {
    await app.close();
  });

  it('reports healthy', async () => {
    const res = await request(http).get('/api/v1/health').expect(200);
    expect(res.body.status).toBe('ok');
    expect(res.body.database).toBe('up');
  });

  it('rejects unauthenticated access', async () => {
    await request(http).get('/api/v1/assets').expect(401);
  });

  it('registers a tenant with its administrator', async () => {
    const res = await request(http)
      .post('/api/v1/auth/register-organization')
      .send({
        organizationName: 'Acme Corporation',
        organizationSlug: 'acme',
        adminEmail: 'admin@acme.com',
        adminFullName: 'Jane Admin',
        adminPassword: 'Sup3r-secret-pass!',
      })
      .expect(201);
    expect(res.body.accessToken).toBeDefined();
    expect(res.body.user.role).toBe('Organization Administrator');
    token = res.body.accessToken;
  });

  it('logs in and refreshes tokens', async () => {
    const login = await request(http)
      .post('/api/v1/auth/login')
      .send({ email: 'admin@acme.com', password: 'Sup3r-secret-pass!' })
      .expect(200);
    token = login.body.accessToken;

    const refreshed = await request(http)
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: login.body.refreshToken })
      .expect(200);
    expect(refreshed.body.accessToken).toBeDefined();

    // Rotation: the old refresh token is now revoked.
    await request(http)
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: login.body.refreshToken })
      .expect(401);
    token = refreshed.body.accessToken;
  });

  it('creates the org structure', async () => {
    branchId = (
      await request(http)
        .post('/api/v1/branches')
        .set(auth())
        .send({ name: 'Headquarters', code: 'HQ', city: 'Berlin', country: 'DE' })
        .expect(201)
    ).body.id;

    departmentId = (
      await request(http)
        .post('/api/v1/departments')
        .set(auth())
        .send({ name: 'Engineering', code: 'ENG', branchId })
        .expect(201)
    ).body.id;

    categoryId = (
      await request(http)
        .post('/api/v1/categories')
        .set(auth())
        .send({
          name: 'Laptops',
          code: 'LAP',
          usefulLifeYears: 4,
          customFieldDefinitions: [
            { key: 'keyboardLayout', label: 'Keyboard layout', type: 'select', options: ['US', 'DE'] },
          ],
        })
        .expect(201)
    ).body.id;

    employeeId = (
      await request(http)
        .post('/api/v1/employees')
        .set(auth())
        .send({
          employeeNumber: 'EMP-0001',
          fullName: 'Erika Mustermann',
          email: 'erika@acme.com',
          departmentId,
          branchId,
        })
        .expect(201)
    ).body.id;
  });

  it('creates an asset with generated tag and validated custom fields', async () => {
    // Unknown custom field is rejected
    await request(http)
      .post('/api/v1/assets')
      .set(auth())
      .send({ name: 'Bad', categoryId, customFields: { nope: 1 } })
      .expect(400);

    const res = await request(http)
      .post('/api/v1/assets')
      .set(auth())
      .send({
        name: 'MacBook Pro 16"',
        categoryId,
        serialNumber: 'C02XL0GYJGH5',
        manufacturer: 'Apple',
        model: 'A2485',
        branchId,
        departmentId,
        purchaseDate: '2024-01-15',
        purchaseCost: 3200,
        warrantyStartDate: '2024-01-15',
        warrantyEndDate: '2027-01-15',
        customFields: { keyboardLayout: 'DE' },
      })
      .expect(201);
    assetId = res.body.id;
    assetTag = res.body.assetTag;
    expect(assetTag).toMatch(/^ACME-\d{6}$/);
  });

  it('resolves scanned codes and serves QR/barcode labels', async () => {
    const scan = await request(http)
      .get(`/api/v1/assets/scan/${assetTag}`)
      .set(auth())
      .expect(200);
    expect(scan.body.id).toBe(assetId);

    const qr = await request(http).get(`/api/v1/assets/${assetId}/qrcode`).set(auth()).expect(200);
    expect(qr.headers['content-type']).toBe('image/png');
    expect(qr.body.length).toBeGreaterThan(100);

    const barcode = await request(http)
      .get(`/api/v1/assets/${assetId}/barcode`)
      .set(auth())
      .expect(200);
    expect(barcode.headers['content-type']).toBe('image/png');
  });

  it('computes straight-line depreciation', async () => {
    const res = await request(http).get(`/api/v1/assets/${assetId}`).set(auth()).expect(200);
    expect(res.body.depreciation.method).toBe('straight-line');
    expect(res.body.depreciation.currentBookValue).toBeLessThan(3200);
    expect(res.body.depreciation.currentBookValue).toBeGreaterThan(0);
  });

  it('enforces the lifecycle state machine', async () => {
    await request(http)
      .post(`/api/v1/assets/${assetId}/transition`)
      .set(auth())
      .send({ status: 'DISPOSED' })
      .expect(400); // IN_STOCK → DISPOSED is illegal

    await request(http)
      .post(`/api/v1/assets/${assetId}/transition`)
      .set(auth())
      .send({ status: 'DEPLOYED', reason: 'Imaging complete' })
      .expect(201);
  });

  it('checks the asset out to an employee and back in', async () => {
    const out = await request(http)
      .post('/api/v1/assignments/check-out')
      .set(auth())
      .send({
        assetId,
        employeeId,
        expectedReturnAt: '2030-01-01T00:00:00.000Z',
        signature: 'data:image/png;base64,AAAA',
        notes: 'New starter kit',
      })
      .expect(201);
    assignmentId = out.body.id;

    // Double check-out is rejected
    await request(http)
      .post('/api/v1/assignments/check-out')
      .set(auth())
      .send({ assetId, employeeId })
      .expect(400);

    const held = await request(http)
      .get(`/api/v1/assignments/employee/${employeeId}/assets`)
      .set(auth())
      .expect(200);
    expect(held.body).toHaveLength(1);

    await request(http)
      .post(`/api/v1/assignments/${assignmentId}/check-in`)
      .set(auth())
      .send({ condition: 'GOOD', damageNotes: 'Small scratch on lid' })
      .expect(201);

    const asset = await request(http).get(`/api/v1/assets/${assetId}`).set(auth()).expect(200);
    expect(asset.body.status).toBe('IN_STOCK');
    expect(asset.body.assignedEmployeeId).toBeNull();
  });

  it('manages license seats', async () => {
    licenseId = (
      await request(http)
        .post('/api/v1/licenses')
        .set(auth())
        .send({
          name: 'JetBrains All Products',
          vendor: 'JetBrains',
          licenseKey: 'SECRET-KEY-123',
          seats: 1,
          expiryDate: '2030-06-30',
        })
        .expect(201)
    ).body.id;

    const seat = await request(http)
      .post(`/api/v1/licenses/${licenseId}/assign`)
      .set(auth())
      .send({ employeeId })
      .expect(201);

    // Seat pool exhausted
    await request(http)
      .post(`/api/v1/licenses/${licenseId}/assign`)
      .set(auth())
      .send({ assetId })
      .expect(400);

    const detail = await request(http)
      .get(`/api/v1/licenses/${licenseId}`)
      .set(auth())
      .expect(200);
    expect(detail.body.seatsUsed).toBe(1);
    expect(detail.body.seatsRemaining).toBe(0);

    // Keys are hidden in list views
    const list = await request(http).get('/api/v1/licenses').set(auth()).expect(200);
    expect(list.body.items[0].licenseKey).toBeUndefined();

    await request(http)
      .post(`/api/v1/licenses/${licenseId}/seats/${seat.body.id}/release`)
      .set(auth())
      .expect(204);
  });

  it('tracks maintenance work orders', async () => {
    maintenanceId = (
      await request(http)
        .post('/api/v1/maintenance')
        .set(auth())
        .send({
          assetId,
          type: 'PREVENTIVE',
          title: 'Annual service',
          scheduledFor: '2026-08-01',
          cost: 120.5,
        })
        .expect(201)
    ).body.id;

    await request(http)
      .patch(`/api/v1/maintenance/${maintenanceId}`)
      .set(auth())
      .send({ status: 'COMPLETED', resolutionNotes: 'Fans cleaned, thermal paste renewed' })
      .expect(200);

    const history = await request(http)
      .get(`/api/v1/assets/${assetId}/history`)
      .set(auth())
      .expect(200);
    const types = history.body.items.map((e: any) => e.type);
    expect(types).toEqual(
      expect.arrayContaining(['CREATED', 'STATUS_CHANGED', 'CHECKED_OUT', 'CHECKED_IN', 'MAINTENANCE']),
    );
  });

  it('runs an inventory audit with scan reconciliation', async () => {
    auditId = (
      await request(http)
        .post('/api/v1/inventory-audits')
        .set(auth())
        .send({ name: 'Q3 physical inventory', branchId })
        .expect(201)
    ).body.id;

    const matched = await request(http)
      .post(`/api/v1/inventory-audits/${auditId}/scan`)
      .set(auth())
      .send({ code: assetTag })
      .expect(201);
    expect(matched.body.result).toBe('MATCHED');

    const unknown = await request(http)
      .post(`/api/v1/inventory-audits/${auditId}/scan`)
      .set(auth())
      .send({ code: 'NOT-A-REAL-TAG' })
      .expect(201);
    expect(unknown.body.result).toBe('UNKNOWN');

    const completed = await request(http)
      .post(`/api/v1/inventory-audits/${auditId}/complete`)
      .set(auth())
      .expect(201);
    expect(completed.body.results.matched).toBe(1);
    expect(completed.body.results.unknownCodes).toEqual(['NOT-A-REAL-TAG']);
    expect(completed.body.results.missingAssetIds).toHaveLength(0);
  });

  it('serves the executive dashboard', async () => {
    const res = await request(http).get('/api/v1/dashboard').set(auth()).expect(200);
    expect(res.body.totals.totalAssets).toBe(1);
    expect(res.body.financials.totalPurchaseCost).toBe(3200);
    expect(res.body.breakdowns.byStatus.length).toBeGreaterThan(0);
    expect(res.body.recentActivity.length).toBeGreaterThan(0);
  });

  it('generates reports in multiple formats', async () => {
    const json = await request(http)
      .get('/api/v1/reports/asset-inventory?format=json')
      .set(auth())
      .expect(200);
    expect(JSON.parse(json.text).rows).toHaveLength(1);

    const csv = await request(http)
      .get('/api/v1/reports/financial?format=csv')
      .set(auth())
      .expect(200);
    expect(csv.text).toContain('Asset Tag');

    const xlsx = await request(http)
      .get('/api/v1/reports/licenses?format=xlsx')
      .set(auth())
      .expect(200);
    expect(xlsx.headers['content-type']).toContain('spreadsheetml');

    const pdf = await request(http)
      .get('/api/v1/reports/warranty?format=pdf')
      .set(auth())
      .expect(200);
    expect(pdf.headers['content-type']).toBe('application/pdf');
  });

  it('records an audit trail', async () => {
    const res = await request(http)
      .get('/api/v1/audit-logs?pageSize=100')
      .set(auth())
      .expect(200);
    const actions = res.body.items.map((l: any) => l.action);
    expect(actions).toEqual(expect.arrayContaining(['auth.login', 'assets.created']));
  });

  it('enforces RBAC for restricted roles', async () => {
    const roles = await request(http).get('/api/v1/users/roles?pageSize=50').set(auth()).expect(200);
    const readOnly = roles.body.items.find((r: any) => r.name === 'Read-Only User');
    expect(readOnly.isSystem).toBe(true);

    // System roles are immutable
    await request(http)
      .patch(`/api/v1/users/roles/${readOnly.id}`)
      .set(auth())
      .send({ description: 'hack' })
      .expect(400);

    await request(http)
      .post('/api/v1/users')
      .set(auth())
      .send({
        email: 'viewer@acme.com',
        fullName: 'Vera Viewer',
        password: 'another-secret-1!',
        roleId: readOnly.id,
      })
      .expect(201);

    const viewerLogin = await request(http)
      .post('/api/v1/auth/login')
      .send({ email: 'viewer@acme.com', password: 'another-secret-1!' })
      .expect(200);
    const viewerToken = viewerLogin.body.accessToken;

    await request(http)
      .get('/api/v1/assets')
      .set({ Authorization: `Bearer ${viewerToken}` })
      .expect(200);
    await request(http)
      .post('/api/v1/assets')
      .set({ Authorization: `Bearer ${viewerToken}` })
      .send({ name: 'Nope', categoryId })
      .expect(403);
  });

  it('isolates tenants completely', async () => {
    const other = await request(http)
      .post('/api/v1/auth/register-organization')
      .send({
        organizationName: 'Globex',
        organizationSlug: 'globex',
        adminEmail: 'admin@globex.com',
        adminFullName: 'Gary Globex',
        adminPassword: 'globex-secret-99!',
      })
      .expect(201);
    const otherToken = other.body.accessToken;

    // Foreign UUIDs resolve to 404 inside the other tenant
    await request(http)
      .get(`/api/v1/assets/${assetId}`)
      .set({ Authorization: `Bearer ${otherToken}` })
      .expect(404);
    const list = await request(http)
      .get('/api/v1/assets')
      .set({ Authorization: `Bearer ${otherToken}` })
      .expect(200);
    expect(list.body.total).toBe(0);
    const scan = await request(http)
      .get(`/api/v1/assets/scan/${assetTag}`)
      .set({ Authorization: `Bearer ${otherToken}` })
      .expect(404);
    expect(scan.body.message).toContain('No asset');
  });

  it('supports logout (refresh revocation)', async () => {
    const login = await request(http)
      .post('/api/v1/auth/login')
      .send({ email: 'admin@acme.com', password: 'Sup3r-secret-pass!' })
      .expect(200);
    await request(http)
      .post('/api/v1/auth/logout')
      .set({ Authorization: `Bearer ${login.body.accessToken}` })
      .expect(204);
    await request(http)
      .post('/api/v1/auth/refresh')
      .send({ refreshToken: login.body.refreshToken })
      .expect(401);
  });
});
