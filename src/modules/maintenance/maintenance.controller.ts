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
} from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { CreateMaintenanceDto, UpdateMaintenanceDto } from './maintenance.dto';
import { MaintenanceStatus } from './maintenance.entity';
import { MaintenanceService } from './maintenance.service';

const [READ, CREATE, UPDATE, DELETE] = PERMISSIONS.MAINTENANCE;

@ApiTags('Maintenance')
@ApiBearerAuth()
@Controller('maintenance')
export class MaintenanceController {
  constructor(private readonly service: MaintenanceService) {}

  @Get()
  @RequirePermissions(READ)
  list(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PageQueryDto,
    @Query('assetId') assetId?: string,
    @Query('status') status?: MaintenanceStatus,
    @Query('search') search?: string,
  ) {
    return this.service.listFiltered(user.organizationId, query, { assetId, status, search });
  }

  @Get(':id')
  @RequirePermissions(READ)
  findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(user.organizationId, id);
  }

  @Post()
  @RequirePermissions(CREATE)
  create(@CurrentUser() user: AuthenticatedUser, @Body() dto: CreateMaintenanceDto) {
    return this.service.createRecord(user.organizationId, dto, user.userId);
  }

  @Patch(':id')
  @RequirePermissions(UPDATE)
  update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateMaintenanceDto,
  ) {
    return this.service.updateRecord(user.organizationId, id, dto, user.userId);
  }

  @Delete(':id')
  @HttpCode(204)
  @RequirePermissions(DELETE)
  remove(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.softDelete(user.organizationId, id);
  }
}
