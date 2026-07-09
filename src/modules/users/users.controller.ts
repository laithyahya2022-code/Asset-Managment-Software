import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Query,
  SerializeOptions,
} from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { ALL_PERMISSIONS, PERMISSIONS } from '../../common/security/permissions';
import { CreateRoleDto, CreateUserDto, UpdateRoleDto, UpdateUserDto } from './dto/user.dto';
import { UsersService } from './users.service';

const [USERS_READ, USERS_CREATE, USERS_UPDATE, USERS_DELETE] = PERMISSIONS.USERS;
const [ROLES_READ, ROLES_CREATE, ROLES_UPDATE, ROLES_DELETE] = PERMISSIONS.ROLES;

@ApiTags('Users & Roles')
@ApiBearerAuth()
@Controller('users')
@SerializeOptions({ excludePrefixes: ['passwordHash', 'refreshTokenHash'] })
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Get()
  @RequirePermissions(USERS_READ)
  list(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PageQueryDto,
    @Query('search') search?: string,
  ) {
    return this.usersService.list(user.organizationId, query, search);
  }

  @Get('permissions/catalog')
  @RequirePermissions(ROLES_READ)
  permissionCatalog() {
    return ALL_PERMISSIONS;
  }

  @Get('roles')
  @RequirePermissions(ROLES_READ)
  listRoles(@CurrentUser() user: AuthenticatedUser, @Query() query: PageQueryDto) {
    return this.usersService.listRoles(user.organizationId, query);
  }

  @Post('roles')
  @RequirePermissions(ROLES_CREATE)
  createRole(@CurrentUser() user: AuthenticatedUser, @Body() dto: CreateRoleDto) {
    return this.usersService.createRole(user.organizationId, dto);
  }

  @Patch('roles/:id')
  @RequirePermissions(ROLES_UPDATE)
  updateRole(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateRoleDto,
  ) {
    return this.usersService.updateRole(user.organizationId, id, dto);
  }

  @Delete('roles/:id')
  @HttpCode(204)
  @RequirePermissions(ROLES_DELETE)
  deleteRole(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.usersService.deleteRole(user.organizationId, id);
  }

  @Get(':id')
  @RequirePermissions(USERS_READ)
  findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.usersService.findOne(user.organizationId, id);
  }

  @Post()
  @RequirePermissions(USERS_CREATE)
  create(@CurrentUser() user: AuthenticatedUser, @Body() dto: CreateUserDto) {
    return this.usersService.createUser(user.organizationId, dto);
  }

  @Patch(':id')
  @RequirePermissions(USERS_UPDATE)
  update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateUserDto,
  ) {
    return this.usersService.updateUser(user.organizationId, id, dto);
  }

  @Delete(':id')
  @HttpCode(204)
  @RequirePermissions(USERS_DELETE)
  remove(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.usersService.softDelete(user.organizationId, id);
  }
}
