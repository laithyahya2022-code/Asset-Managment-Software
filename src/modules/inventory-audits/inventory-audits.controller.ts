import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
  Query,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { IsNotEmpty, IsOptional, IsString, IsUUID, MaxLength } from 'class-validator';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { InventoryAuditsService } from './inventory-audits.service';

class StartAuditDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  name: string;

  @IsOptional()
  @IsUUID()
  branchId?: string;
}

class ScanDto {
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  code: string;

  @IsOptional()
  @IsString()
  @MaxLength(300)
  locationNote?: string;
}

const [READ, CREATE, UPDATE] = PERMISSIONS.INVENTORY_AUDITS;

@ApiTags('Inventory Audits')
@ApiBearerAuth()
@Controller('inventory-audits')
export class InventoryAuditsController {
  constructor(private readonly service: InventoryAuditsService) {}

  @Get()
  @RequirePermissions(READ)
  list(@CurrentUser() user: AuthenticatedUser, @Query() query: PageQueryDto) {
    return this.service.list(user.organizationId, query);
  }

  @Get(':id')
  @RequirePermissions(READ)
  findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.findOne(user.organizationId, id);
  }

  @Get(':id/scans')
  @RequirePermissions(READ)
  scans(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Query() query: PageQueryDto,
  ) {
    return this.service.listScans(user.organizationId, id, query);
  }

  @Post()
  @RequirePermissions(CREATE)
  @ApiOperation({ summary: 'Start an audit session (snapshots expected assets)' })
  start(@CurrentUser() user: AuthenticatedUser, @Body() dto: StartAuditDto) {
    return this.service.start(user.organizationId, dto, user.userId);
  }

  @Post(':id/scan')
  @RequirePermissions(PERMISSIONS.INVENTORY_AUDITS_SCAN)
  @ApiOperation({ summary: 'Register a QR/barcode scan; returns live classification' })
  scan(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: ScanDto,
  ) {
    return this.service.scan(user.organizationId, id, dto, user.userId);
  }

  @Post(':id/complete')
  @RequirePermissions(UPDATE)
  @ApiOperation({ summary: 'Close the session and compute missing/moved/unknown' })
  complete(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.complete(user.organizationId, id, user.userId);
  }

  @Post(':id/cancel')
  @RequirePermissions(UPDATE)
  cancel(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.service.cancel(user.organizationId, id);
  }
}
