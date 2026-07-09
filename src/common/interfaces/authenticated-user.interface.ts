/** Shape of the principal attached to every authenticated request. */
export interface AuthenticatedUser {
  userId: string;
  organizationId: string;
  email: string;
  fullName: string;
  roleId: string;
  roleName: string;
  permissions: string[];
}
