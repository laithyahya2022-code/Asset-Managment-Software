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
  Res,
} from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { InjectRepository } from '@nestjs/typeorm';
import { Response } from 'express';
import { Repository } from 'typeorm';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { PageQueryDto } from '../../common/dto/page-query.dto';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import { Organization } from '../organizations/organization.entity';
import { AssetFilterDto, CreateAssetDto, TransitionAssetDto, UpdateAssetDto } from './asset.dto';
import { AssetsService } from './assets.service';
import { LabelsService } from './labels.service';

const [READ, CREATE, UPDATE, DELETE] = PERMISSIONS.ASSETS;

@ApiTags('Assets')
@ApiBearerAuth()
@Controller('assets')
export class AssetsController {
  constructor(
    private readonly assetsService: AssetsService,
    private readonly labelsService: LabelsService,
    @InjectRepository(Organization)
    private readonly organizations: Repository<Organization>,
  ) {}

  @Get()
  @RequirePermissions(READ)
  @ApiOperation({ summary: 'Search and filter the asset inventory' })
  list(
    @CurrentUser() user: AuthenticatedUser,
    @Query() query: PageQueryDto,
    @Query() filters: AssetFilterDto,
  ) {
    return this.assetsService.search(user.organizationId, query, filters);
  }

  @Get('scan/:code')
  @RequirePermissions(READ)
  @ApiOperation({ summary: 'Resolve a scanned QR/barcode payload to an asset' })
  scan(@CurrentUser() user: AuthenticatedUser, @Param('code') code: string) {
    return this.assetsService.findByCode(user.organizationId, code);
  }

  @Get(':id')
  @RequirePermissions(READ)
  async findOne(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    const asset = await this.assetsService.findOne(user.organizationId, id);
    return { ...asset, depreciation: this.assetsService.depreciation(asset) };
  }

  @Get(':id/history')
  @RequirePermissions(READ)
  history(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Query() query: PageQueryDto,
  ) {
    return this.assetsService.history(user.organizationId, id, query);
  }

  @Get(':id/qrcode')
  @RequirePermissions(READ)
  @ApiOperation({ summary: 'PNG QR code label for the asset' })
  async qrcode(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Res() res: Response,
  ) {
    const asset = await this.assetsService.findOne(user.organizationId, id);
    const png = await this.labelsService.qrCodePng(asset.assetTag);
    res.setHeader('Content-Type', 'image/png');
    res.setHeader('Content-Disposition', `inline; filename="${asset.assetTag}-qr.png"`);
    res.send(png);
  }

  @Get(':id/barcode')
  @RequirePermissions(READ)
  @ApiOperation({ summary: 'PNG Code-128 barcode label for the asset' })
  async barcode(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Res() res: Response,
  ) {
    const asset = await this.assetsService.findOne(user.organizationId, id);
    const png = await this.labelsService.barcodePng(asset.assetTag);
    res.setHeader('Content-Type', 'image/png');
    res.setHeader('Content-Disposition', `inline; filename="${asset.assetTag}-barcode.png"`);
    res.send(png);
  }

  @Post()
  @RequirePermissions(CREATE)
  async create(@CurrentUser() user: AuthenticatedUser, @Body() dto: CreateAssetDto) {
    const org = await this.organizations.findOne({ where: { id: user.organizationId } });
    return this.assetsService.createAsset(
      user.organizationId,
      dto,
      user.userId,
      org?.settings?.assetTagPrefix,
    );
  }

  @Patch(':id')
  @RequirePermissions(UPDATE)
  update(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateAssetDto,
  ) {
    return this.assetsService.updateAsset(user.organizationId, id, dto, user.userId);
  }

  @Post(':id/transition')
  @RequirePermissions(PERMISSIONS.ASSETS_TRANSITION)
  @ApiOperation({ summary: 'Move the asset through its lifecycle state machine' })
  transition(
    @CurrentUser() user: AuthenticatedUser,
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: TransitionAssetDto,
  ) {
    return this.assetsService.transition(user.organizationId, id, dto, user.userId);
  }

  @Delete(':id')
  @HttpCode(204)
  @RequirePermissions(DELETE)
  remove(@CurrentUser() user: AuthenticatedUser, @Param('id', ParseUUIDPipe) id: string) {
    return this.assetsService.softDelete(user.organizationId, id);
  }
}
