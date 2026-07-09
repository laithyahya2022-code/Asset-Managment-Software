import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { APP_GUARD } from '@nestjs/core';
import { ScheduleModule } from '@nestjs/schedule';
import { ThrottlerGuard, ThrottlerModule } from '@nestjs/throttler';
import configuration from './config/configuration';
import { DatabaseModule } from './database/database.module';
import { HealthController } from './health.controller';
import { JwtAuthGuard } from './common/guards/jwt-auth.guard';
import { PermissionsGuard } from './common/guards/permissions.guard';
import { AssetsModule } from './modules/assets/assets.module';
import { AssignmentsModule } from './modules/assignments/assignments.module';
import { AuditLogModule } from './modules/audit-log/audit-log.module';
import { AuthModule } from './modules/auth/auth.module';
import { BranchesModule } from './modules/branches/branches.module';
import { CategoriesModule } from './modules/categories/categories.module';
import { DashboardModule } from './modules/dashboard/dashboard.module';
import { DepartmentsModule } from './modules/departments/departments.module';
import { EmployeesModule } from './modules/employees/employees.module';
import { InventoryAuditsModule } from './modules/inventory-audits/inventory-audits.module';
import { LicensesModule } from './modules/licenses/licenses.module';
import { MaintenanceModule } from './modules/maintenance/maintenance.module';
import { NotificationsModule } from './modules/notifications/notifications.module';
import { OrganizationsModule } from './modules/organizations/organizations.module';
import { ReportsModule } from './modules/reports/reports.module';
import { SuppliersModule } from './modules/suppliers/suppliers.module';
import { UsersModule } from './modules/users/users.module';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true, load: [configuration] }),
    ThrottlerModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        throttlers: [
          {
            ttl: config.get<number>('throttle.ttlMs') ?? 60_000,
            limit: config.get<number>('throttle.limit') ?? 120,
          },
        ],
      }),
    }),
    ScheduleModule.forRoot(),
    DatabaseModule,
    AuditLogModule,
    AuthModule,
    OrganizationsModule,
    UsersModule,
    BranchesModule,
    DepartmentsModule,
    SuppliersModule,
    EmployeesModule,
    CategoriesModule,
    AssetsModule,
    AssignmentsModule,
    LicensesModule,
    MaintenanceModule,
    InventoryAuditsModule,
    NotificationsModule,
    DashboardModule,
    ReportsModule,
  ],
  controllers: [HealthController],
  providers: [
    // Order matters: throttling → authentication → authorization.
    { provide: APP_GUARD, useClass: ThrottlerGuard },
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_GUARD, useClass: PermissionsGuard },
  ],
})
export class AppModule {}
