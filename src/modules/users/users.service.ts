import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { InjectRepository } from '@nestjs/typeorm';
import * as bcrypt from 'bcryptjs';
import { Repository } from 'typeorm';
import { Page, PageQueryDto } from '../../common/dto/page-query.dto';
import { TenantCrudService } from '../../common/services/tenant-crud.service';
import { CreateUserDto, UpdateUserDto } from './dto/user.dto';
import { Role } from './role.entity';
import { User } from './user.entity';

@Injectable()
export class UsersService extends TenantCrudService<User> {
  constructor(
    @InjectRepository(User) repository: Repository<User>,
    @InjectRepository(Role) private readonly roles: Repository<Role>,
    private readonly config: ConfigService,
  ) {
    super(repository, 'User', ['email', 'fullName'], ['createdAt', 'email', 'fullName']);
  }

  async createUser(organizationId: string, dto: CreateUserDto): Promise<User> {
    await this.assertRoleInTenant(organizationId, dto.roleId);
    const duplicate = await this.repository.findOne({
      where: { organizationId, email: dto.email.toLowerCase() },
      withDeleted: true,
    });
    if (duplicate) throw new ConflictException('A user with this email already exists');

    const { password, ...rest } = dto;
    return this.create(organizationId, {
      ...rest,
      email: dto.email.toLowerCase(),
      passwordHash: await bcrypt.hash(
        password,
        this.config.get<number>('security.bcryptRounds') ?? 10,
      ),
    });
  }

  async updateUser(organizationId: string, id: string, dto: UpdateUserDto): Promise<User> {
    const { password, ...rest } = dto;
    const patch: Partial<User> = { ...rest };
    if (dto.roleId) await this.assertRoleInTenant(organizationId, dto.roleId);
    if (dto.email) patch.email = dto.email.toLowerCase();
    if (password) {
      patch.passwordHash = await bcrypt.hash(
        password,
        this.config.get<number>('security.bcryptRounds') ?? 10,
      );
      patch.refreshTokenHash = null;
    }
    return this.update(organizationId, id, patch);
  }

  listRoles(organizationId: string, query: PageQueryDto): Promise<Page<Role>> {
    return this.roles
      .findAndCount({
        where: { organizationId },
        order: { name: 'ASC' },
        skip: (query.page - 1) * query.pageSize,
        take: query.pageSize,
      })
      .then(([items, total]) => ({
        items,
        total,
        page: query.page,
        pageSize: query.pageSize,
        totalPages: Math.max(1, Math.ceil(total / query.pageSize)),
      }));
  }

  async createRole(organizationId: string, dto: { name: string; description?: string; permissions: string[] }) {
    return this.roles.save(this.roles.create({ ...dto, organizationId, isSystem: false }));
  }

  async updateRole(organizationId: string, id: string, dto: Partial<Role>) {
    const role = await this.findRole(organizationId, id);
    if (role.isSystem) throw new BadRequestException('System roles cannot be modified');
    const { organizationId: _o, id: _i, isSystem: _s, ...patch } = dto as any;
    Object.assign(role, patch);
    return this.roles.save(role);
  }

  async deleteRole(organizationId: string, id: string): Promise<void> {
    const role = await this.findRole(organizationId, id);
    if (role.isSystem) throw new BadRequestException('System roles cannot be deleted');
    const inUse = await this.repository.count({ where: { organizationId, roleId: id } });
    if (inUse > 0) throw new BadRequestException('Role is assigned to users');
    await this.roles.softRemove(role);
  }

  private async findRole(organizationId: string, id: string): Promise<Role> {
    const role = await this.roles.findOne({ where: { id, organizationId } });
    if (!role) throw new NotFoundException('Role not found');
    return role;
  }

  private async assertRoleInTenant(organizationId: string, roleId: string): Promise<void> {
    await this.findRole(organizationId, roleId);
  }
}
