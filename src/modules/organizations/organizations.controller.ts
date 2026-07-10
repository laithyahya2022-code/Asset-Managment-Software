import { Body, Controller, Get, NotFoundException, Patch } from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { InjectRepository } from '@nestjs/typeorm';
import { IsObject, IsOptional, IsString, MaxLength } from 'class-validator';
import { Repository } from 'typeorm';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { Organization } from './organization.entity';

class UpdateOrganizationDto {
  @IsOptional()
  @IsString()
  @MaxLength(200)
  name?: string;

  @IsOptional()
  @IsString()
  @MaxLength(320)
  contactEmail?: string;

  @IsOptional()
  @IsString()
  @MaxLength(100)
  country?: string;

  @IsOptional()
  @IsString()
  @MaxLength(10)
  currency?: string;

  @IsOptional()
  @IsObject()
  settings?: Organization['settings'];
}

/**
 * Tenants manage only their own organization; the slug and isActive flag
 * are platform-operator concerns and are not exposed here.
 */
@ApiTags('Organization')
@ApiBearerAuth()
@Controller('organization')
export class OrganizationsController {
  constructor(
    @InjectRepository(Organization)
    private readonly organizations: Repository<Organization>,
  ) {}

  @Get()
  @RequirePermissions(PERMISSIONS.ORGANIZATION_READ)
  async get(@CurrentUser() user: AuthenticatedUser) {
    const org = await this.organizations.findOne({ where: { id: user.organizationId } });
    if (!org) throw new NotFoundException('Organization not found');
    return org;
  }

  @Patch()
  @RequirePermissions(PERMISSIONS.ORGANIZATION_UPDATE)
  async update(@CurrentUser() user: AuthenticatedUser, @Body() dto: UpdateOrganizationDto) {
    const org = await this.get(user);
    Object.assign(org, dto, { settings: { ...org.settings, ...dto.settings } });
    return this.organizations.save(org);
  }
}
