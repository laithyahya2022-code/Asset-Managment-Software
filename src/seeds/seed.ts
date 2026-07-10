/**
 * Demo data seeder. Boots the application context and provisions a sample
 * tenant through the same services the API uses (so every rule applies).
 *
 *   DB_SYNCHRONIZE=true npm run seed
 */
import { NestFactory } from '@nestjs/core';
import { Logger } from '@nestjs/common';
import { AppModule } from '../app.module';
import { AuthService } from '../modules/auth/auth.service';
import { BranchesService } from '../modules/branches/branches.module';
import { CategoriesService } from '../modules/categories/categories.module';
import { DepartmentsService } from '../modules/departments/departments.module';
import { EmployeesService } from '../modules/employees/employees.module';
import { AssetsService } from '../modules/assets/assets.service';
import { AssetCondition, AssetStatus } from '../modules/assets/asset-lifecycle';
import { LicensesService } from '../modules/licenses/licenses.service';

async function seed(): Promise<void> {
  const logger = new Logger('Seed');
  const app = await NestFactory.createApplicationContext(AppModule);

  const auth = app.get(AuthService);
  const session = await auth.registerOrganization({
    organizationName: 'Demo Organization',
    organizationSlug: 'demo',
    adminEmail: 'admin@demo.local',
    adminFullName: 'Demo Admin',
    adminPassword: 'Demo-Passw0rd!',
  });
  const orgId = session.user.organizationId;
  const adminId = session.user.id;
  logger.log(`Tenant "demo" created — login admin@demo.local / Demo-Passw0rd!`);

  const branches = app.get(BranchesService);
  const hq = await branches.create(orgId, { name: 'Headquarters', code: 'HQ', city: 'Riyadh' });
  const plant = await branches.create(orgId, { name: 'North Campus', code: 'NC', city: 'Jeddah' });

  const departments = app.get(DepartmentsService);
  const it = await departments.create(orgId, { name: 'IT', code: 'IT', branchId: hq.id });
  const fin = await departments.create(orgId, { name: 'Finance', code: 'FIN', branchId: hq.id });

  const categories = app.get(CategoriesService);
  const catDefs = [
    { name: 'Laptops', code: 'LAP', usefulLifeYears: 4 },
    { name: 'Desktops', code: 'DTP', usefulLifeYears: 5 },
    { name: 'Monitors', code: 'MON', usefulLifeYears: 6 },
    { name: 'Printers', code: 'PRN', usefulLifeYears: 5 },
    { name: 'Servers', code: 'SRV', usefulLifeYears: 7 },
    { name: 'Network Equipment', code: 'NET', usefulLifeYears: 7 },
    { name: 'Smartphones', code: 'PHN', usefulLifeYears: 3 },
  ];
  const cats: Record<string, string> = {};
  for (const def of catDefs) {
    cats[def.code] = (await categories.create(orgId, def)).id;
  }

  const employees = app.get(EmployeesService);
  const emp1 = await employees.create(orgId, {
    employeeNumber: 'EMP-0001',
    fullName: 'Sara Al-Fulan',
    email: 'sara@demo.local',
    jobTitle: 'Software Engineer',
    departmentId: it.id,
    branchId: hq.id,
  });
  await employees.create(orgId, {
    employeeNumber: 'EMP-0002',
    fullName: 'Omar Haddad',
    email: 'omar@demo.local',
    jobTitle: 'Accountant',
    departmentId: fin.id,
    branchId: plant.id,
  });

  const assets = app.get(AssetsService);
  const demoAssets = [
    { name: 'ThinkPad X1 Carbon G11', cat: 'LAP', cost: 1900, mfr: 'Lenovo' },
    { name: 'MacBook Pro 14"', cat: 'LAP', cost: 2400, mfr: 'Apple' },
    { name: 'Dell OptiPlex 7010', cat: 'DTP', cost: 950, mfr: 'Dell' },
    { name: 'Dell U2723QE Monitor', cat: 'MON', cost: 550, mfr: 'Dell' },
    { name: 'HP LaserJet Pro M404', cat: 'PRN', cost: 380, mfr: 'HP' },
    { name: 'PowerEdge R760 (VM host)', cat: 'SRV', cost: 14500, mfr: 'Dell' },
    { name: 'Catalyst 9300 Switch', cat: 'NET', cost: 6200, mfr: 'Cisco' },
    { name: 'iPhone 15 Pro', cat: 'PHN', cost: 1100, mfr: 'Apple' },
  ];
  for (const [index, a] of demoAssets.entries()) {
    const purchased = new Date(Date.now() - (index + 4) * 90 * 86_400_000);
    const warrantyEnd = new Date(purchased.getTime() + 3 * 365 * 86_400_000);
    await assets.createAsset(
      orgId,
      {
        name: a.name,
        categoryId: cats[a.cat],
        manufacturer: a.mfr,
        serialNumber: `SN-${1000 + index}`,
        branchId: hq.id,
        departmentId: it.id,
        status: AssetStatus.IN_STOCK,
        condition: AssetCondition.GOOD,
        purchaseDate: purchased.toISOString(),
        purchaseCost: a.cost,
        warrantyStartDate: purchased.toISOString(),
        warrantyEndDate: warrantyEnd.toISOString(),
      },
      adminId,
      'DEMO',
    );
  }
  logger.log(`${demoAssets.length} assets created (employee ${emp1.fullName} ready for check-out)`);

  const licenses = app.get(LicensesService);
  await licenses.create(orgId, {
    name: 'Microsoft 365 E3',
    vendor: 'Microsoft',
    seats: 50,
    type: 'SUBSCRIPTION',
    expiryDate: new Date(Date.now() + 200 * 86_400_000),
    purchaseCost: 18000,
  } as never);

  logger.log('Seed complete.');
  await app.close();
}

void seed();
