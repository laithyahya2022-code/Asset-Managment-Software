import { BadRequestException, Controller, Get, Param, Query, Res } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiParam, ApiQuery, ApiTags } from '@nestjs/swagger';
import { Response } from 'express';
import { CurrentUser } from '../../common/decorators/current-user.decorator';
import { RequirePermissions } from '../../common/decorators/require-permissions.decorator';
import { AuthenticatedUser } from '../../common/interfaces/authenticated-user.interface';
import { PERMISSIONS } from '../../common/security/permissions';
import {
  EXPORT_CONTENT_TYPES,
  ExportFormat,
  ExportService,
} from './export.service';
import { REPORT_TYPES, ReportsService, ReportType } from './reports.service';

@ApiTags('Reports')
@ApiBearerAuth()
@Controller('reports')
export class ReportsController {
  constructor(
    private readonly reportsService: ReportsService,
    private readonly exportService: ExportService,
  ) {}

  @Get()
  @RequirePermissions(PERMISSIONS.REPORTS_GENERATE)
  @ApiOperation({ summary: 'List available report types' })
  types() {
    return { types: REPORT_TYPES, formats: Object.keys(EXPORT_CONTENT_TYPES) };
  }

  @Get(':type')
  @RequirePermissions(PERMISSIONS.REPORTS_GENERATE)
  @ApiOperation({ summary: 'Generate a report in csv, xlsx, pdf or json' })
  @ApiParam({ name: 'type', enum: REPORT_TYPES })
  @ApiQuery({ name: 'format', enum: ['csv', 'xlsx', 'pdf', 'json'], required: false })
  async generate(
    @CurrentUser() user: AuthenticatedUser,
    @Param('type') type: string,
    @Res() res: Response,
    @Query('format') format: ExportFormat = 'json',
  ) {
    if (!REPORT_TYPES.includes(type as ReportType)) {
      throw new BadRequestException(
        `Unknown report type "${type}". Available: ${REPORT_TYPES.join(', ')}`,
      );
    }
    if (!EXPORT_CONTENT_TYPES[format]) {
      throw new BadRequestException(
        `Unknown format "${format}". Available: ${Object.keys(EXPORT_CONTENT_TYPES).join(', ')}`,
      );
    }
    const report = await this.reportsService.build(user.organizationId, type as ReportType);
    const buffer = await this.exportService.render(report, format);
    res.setHeader('Content-Type', EXPORT_CONTENT_TYPES[format]);
    if (format !== 'json') {
      res.setHeader(
        'Content-Disposition',
        `attachment; filename="${type}-${new Date().toISOString().slice(0, 10)}.${format}"`,
      );
    }
    res.send(buffer);
  }
}
