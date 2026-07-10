/**
 * Permission catalog — the single source of truth for RBAC.
 *
 * Permissions follow the `resource:action` convention. Roles are simply
 * named sets of permissions, so custom roles can be composed freely by
 * tenant administrators without code changes.
 */

const crud = (resource: string): string[] => [
  `${resource}:read`,
  `${resource}:create`,
  `${resource}:update`,
  `${resource}:delete`,
];

export const PERMISSIONS = {
  ORGANIZATION_READ: 'organization:read',
  ORGANIZATION_UPDATE: 'organization:update',
  USERS: crud('users'),
  ROLES: crud('roles'),
  BRANCHES: crud('branches'),
  DEPARTMENTS: crud('departments'),
  EMPLOYEES: crud('employees'),
  SUPPLIERS: crud('suppliers'),
  CATEGORIES: crud('categories'),
  ASSETS: crud('assets'),
  ASSETS_TRANSITION: 'assets:transition',
  ASSIGNMENTS_READ: 'assignments:read',
  ASSIGNMENTS_CHECKOUT: 'assignments:checkout',
  ASSIGNMENTS_CHECKIN: 'assignments:checkin',
  LICENSES: crud('licenses'),
  LICENSES_ASSIGN: 'licenses:assign',
  MAINTENANCE: crud('maintenance'),
  INVENTORY_AUDITS: crud('inventory-audits'),
  INVENTORY_AUDITS_SCAN: 'inventory-audits:scan',
  AUDIT_LOGS_READ: 'audit-logs:read',
  REPORTS_GENERATE: 'reports:generate',
  DASHBOARD_READ: 'dashboard:read',
} as const;

export const ALL_PERMISSIONS: string[] = Object.values(PERMISSIONS).flat();

const READ_ONLY: string[] = ALL_PERMISSIONS.filter((p) => p.endsWith(':read'));

/**
 * System roles seeded into every new organization. `isSystem` roles cannot
 * be edited or deleted; tenants may add custom roles alongside them.
 */
export const SYSTEM_ROLES: Array<{
  name: string;
  description: string;
  permissions: string[];
}> = [
  {
    name: 'Organization Administrator',
    description: 'Full control over the organization tenant.',
    permissions: ALL_PERMISSIONS,
  },
  {
    name: 'IT Manager',
    description: 'Manages assets, people and processes; no user/role administration.',
    permissions: ALL_PERMISSIONS.filter(
      (p) => !p.startsWith('users:') && !p.startsWith('roles:') && p !== PERMISSIONS.ORGANIZATION_UPDATE,
    ),
  },
  {
    name: 'IT Technician',
    description: 'Day-to-day asset operations, maintenance and check-in/out.',
    permissions: [
      ...READ_ONLY,
      ...PERMISSIONS.ASSETS,
      PERMISSIONS.ASSETS_TRANSITION,
      PERMISSIONS.ASSIGNMENTS_CHECKOUT,
      PERMISSIONS.ASSIGNMENTS_CHECKIN,
      ...PERMISSIONS.MAINTENANCE,
      PERMISSIONS.INVENTORY_AUDITS_SCAN,
    ],
  },
  {
    name: 'Inventory Staff',
    description: 'Physical inventory and audit scanning.',
    permissions: [
      ...READ_ONLY,
      ...PERMISSIONS.INVENTORY_AUDITS,
      PERMISSIONS.INVENTORY_AUDITS_SCAN,
    ],
  },
  {
    name: 'Auditor',
    description: 'Read-everything role including audit logs and reports.',
    permissions: [...READ_ONLY, PERMISSIONS.AUDIT_LOGS_READ, PERMISSIONS.REPORTS_GENERATE],
  },
  {
    name: 'Department Manager',
    description: 'Read access plus approval-oriented views for a department.',
    permissions: READ_ONLY,
  },
  {
    name: 'Employee',
    description: 'Self-service: sees own assignments and reports issues.',
    permissions: [],
  },
  {
    name: 'Read-Only User',
    description: 'Read-only access to inventory data.',
    permissions: READ_ONLY,
  },
];
