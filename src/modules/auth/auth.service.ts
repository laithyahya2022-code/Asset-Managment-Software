import {
  BadRequestException,
  ConflictException,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import { InjectRepository } from '@nestjs/typeorm';
import * as bcrypt from 'bcryptjs';
import { createHash, randomUUID, timingSafeEqual } from 'crypto';
import { DataSource, Repository } from 'typeorm';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { SYSTEM_ROLES } from '../../common/security/permissions';
import { AuditLogService } from '../audit-log/audit-log.service';
import { Organization } from '../organizations/organization.entity';
import { Role } from '../users/role.entity';
import { User } from '../users/user.entity';
import {
  ChangePasswordDto,
  LoginDto,
  RefreshTokenDto,
  RegisterOrganizationDto,
} from './dto/auth.dto';

export interface TokenPair {
  accessToken: string;
  refreshToken: string;
}

@Injectable()
export class AuthService {
  constructor(
    @InjectRepository(User) private readonly users: Repository<User>,
    @InjectRepository(Organization) private readonly organizations: Repository<Organization>,
    private readonly dataSource: DataSource,
    private readonly jwtService: JwtService,
    private readonly config: ConfigService,
    private readonly auditLog: AuditLogService,
  ) {}

  /**
   * Tenant bootstrap: atomically creates the organization, seeds the
   * system roles, and creates the first administrator account.
   */
  async registerOrganization(dto: RegisterOrganizationDto) {
    const existing = await this.organizations.findOne({
      where: { slug: dto.organizationSlug },
      withDeleted: true,
    });
    if (existing) throw new ConflictException('Organization slug is already taken');

    const { user, organization } = await this.dataSource.transaction(async (manager) => {
      const organization = await manager.save(
        manager.create(Organization, {
          name: dto.organizationName,
          slug: dto.organizationSlug,
          contactEmail: dto.adminEmail,
          settings: {
            assetTagPrefix: dto.organizationSlug.toUpperCase().replace(/-/g, '').slice(0, 6),
            warrantyAlertDays: [90, 60, 30, 7],
            licenseAlertDays: [90, 60, 30, 7],
          },
        }),
      );

      const roles = await manager.save(
        SYSTEM_ROLES.map((r) =>
          manager.create(Role, { ...r, organizationId: organization.id, isSystem: true }),
        ),
      );
      const adminRole = roles.find((r) => r.name === 'Organization Administrator')!;

      const user = await manager.save(
        manager.create(User, {
          organizationId: organization.id,
          email: dto.adminEmail.toLowerCase(),
          fullName: dto.adminFullName,
          passwordHash: await this.hash(dto.adminPassword),
          roleId: adminRole.id,
          role: adminRole,
        }),
      );
      return { user, organization };
    });

    await this.auditLog.record({
      organizationId: organization.id,
      actorUserId: user.id,
      actorEmail: user.email,
      action: 'auth.organization-registered',
      entityType: 'organizations',
      entityId: organization.id,
    });

    return this.issueTokens(user);
  }

  async login(dto: LoginDto) {
    const email = dto.email.toLowerCase();
    let user: User | null;

    if (dto.organizationSlug) {
      const org = await this.organizations.findOne({ where: { slug: dto.organizationSlug } });
      if (!org) throw new UnauthorizedException('Invalid credentials');
      user = await this.users.findOne({ where: { email, organizationId: org.id } });
    } else {
      const matches = await this.users.find({ where: { email }, take: 2 });
      if (matches.length > 1) {
        throw new BadRequestException(
          'Email exists in multiple organizations; provide organizationSlug',
        );
      }
      user = matches[0] ?? null;
    }

    if (!user || !user.isActive || !(await bcrypt.compare(dto.password, user.passwordHash))) {
      await this.auditLog.record({
        organizationId: user?.organizationId ?? null,
        actorEmail: email,
        action: 'auth.login-failed',
      });
      throw new UnauthorizedException('Invalid credentials');
    }

    user.lastLoginAt = new Date();
    await this.users.save(user);
    await this.auditLog.record({
      organizationId: user.organizationId,
      actorUserId: user.id,
      actorEmail: user.email,
      action: 'auth.login',
    });
    return this.issueTokens(user);
  }

  async refresh(dto: RefreshTokenDto): Promise<TokenPair> {
    let payload: { sub: string; org: string };
    try {
      payload = this.jwtService.verify(dto.refreshToken, {
        secret: this.config.get<string>('jwt.refreshSecret'),
      });
    } catch {
      throw new UnauthorizedException('Invalid refresh token');
    }

    const user = await this.users.findOne({
      where: { id: payload.sub, organizationId: payload.org },
    });
    if (
      !user ||
      !user.isActive ||
      !user.refreshTokenHash ||
      !this.tokenMatches(dto.refreshToken, user.refreshTokenHash)
    ) {
      throw new UnauthorizedException('Refresh token has been revoked');
    }
    const tokens = await this.issueTokens(user);
    return { accessToken: tokens.accessToken, refreshToken: tokens.refreshToken };
  }

  async logout(userId: string, organizationId: string): Promise<void> {
    await this.users.update({ id: userId, organizationId }, { refreshTokenHash: null });
    await this.auditLog.record({
      organizationId,
      actorUserId: userId,
      action: 'auth.logout',
    });
  }

  async changePassword(principal: AuthenticatedUser, dto: ChangePasswordDto): Promise<void> {
    const user = await this.users.findOne({
      where: { id: principal.userId, organizationId: principal.organizationId },
    });
    if (!user || !(await bcrypt.compare(dto.currentPassword, user.passwordHash))) {
      throw new UnauthorizedException('Current password is incorrect');
    }
    user.passwordHash = await this.hash(dto.newPassword);
    user.refreshTokenHash = null; // force re-login everywhere
    await this.users.save(user);
    await this.auditLog.record({
      organizationId: user.organizationId,
      actorUserId: user.id,
      actorEmail: user.email,
      action: 'auth.password-changed',
    });
  }

  private async issueTokens(user: User) {
    const accessToken = this.jwtService.sign({
      sub: user.id,
      org: user.organizationId,
      email: user.email,
      name: user.fullName,
      roleId: user.roleId,
      roleName: user.role?.name,
      permissions: user.role?.permissions ?? [],
    });
    // jti guarantees uniqueness even for tokens minted in the same second,
    // which rotation-based revocation depends on.
    const refreshToken = this.jwtService.sign(
      { sub: user.id, org: user.organizationId, tokenType: 'refresh', jti: randomUUID() },
      {
        secret: this.config.get<string>('jwt.refreshSecret'),
        expiresIn: this.config.get<string>('jwt.refreshTtl'),
      },
    );
    // SHA-256 (not bcrypt): JWTs exceed bcrypt's 72-byte limit and share a
    // long common prefix, which would defeat rotation-based revocation.
    user.refreshTokenHash = this.tokenDigest(refreshToken);
    await this.users.save(user);

    return {
      accessToken,
      refreshToken,
      user: {
        id: user.id,
        email: user.email,
        fullName: user.fullName,
        organizationId: user.organizationId,
        role: user.role?.name,
        permissions: user.role?.permissions ?? [],
      },
    };
  }

  private hash(value: string): Promise<string> {
    return bcrypt.hash(value, this.config.get<number>('security.bcryptRounds') ?? 10);
  }

  private tokenDigest(token: string): string {
    return createHash('sha256').update(token).digest('hex');
  }

  private tokenMatches(token: string, storedDigest: string): boolean {
    const digest = Buffer.from(this.tokenDigest(token));
    const stored = Buffer.from(storedDigest);
    return digest.length === stored.length && timingSafeEqual(digest, stored);
  }
}
