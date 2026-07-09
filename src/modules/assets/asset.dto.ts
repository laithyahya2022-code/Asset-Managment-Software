import { ApiProperty, ApiPropertyOptional, PartialType } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import {
  IsArray,
  IsDateString,
  IsEnum,
  IsIn,
  IsInt,
  IsIP,
  IsNotEmpty,
  IsNumber,
  IsObject,
  IsOptional,
  IsString,
  Matches,
  Max,
  MaxLength,
  Min,
  IsUUID,
  ValidateNested,
} from 'class-validator';
import { AssetCondition, AssetStatus } from './asset-lifecycle';

export class AssetAttachmentDto {
  @ApiProperty()
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  name: string;

  @ApiProperty({ description: 'URL in your object store (S3, Azure Blob, …)' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(1000)
  url: string;

  @ApiProperty({ enum: ['image', 'document', 'invoice', 'other'] })
  @IsIn(['image', 'document', 'invoice', 'other'])
  kind: 'image' | 'document' | 'invoice' | 'other';
}

export class CreateAssetDto {
  @ApiPropertyOptional({ description: 'Generated from the tenant prefix when omitted' })
  @IsOptional()
  @IsString()
  @MaxLength(60)
  assetTag?: string;

  @ApiProperty({ example: 'MacBook Pro 16" — Engineering' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(200)
  name: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(120)
  serialNumber?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(120)
  manufacturer?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(120)
  model?: string;

  @ApiProperty()
  @IsUUID()
  categoryId: string;

  @ApiPropertyOptional({ enum: AssetStatus, default: AssetStatus.IN_STOCK })
  @IsOptional()
  @IsEnum(AssetStatus)
  status?: AssetStatus;

  @ApiPropertyOptional({ enum: AssetCondition, default: AssetCondition.GOOD })
  @IsOptional()
  @IsEnum(AssetCondition)
  condition?: AssetCondition;

  @ApiPropertyOptional()
  @IsOptional()
  @IsDateString()
  purchaseDate?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  @Min(0)
  purchaseCost?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsUUID()
  supplierId?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(100)
  purchaseOrderNumber?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(50)
  usefulLifeYears?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsNumber()
  @Min(0)
  salvageValue?: number;

  @ApiPropertyOptional()
  @IsOptional()
  @IsDateString()
  warrantyStartDate?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsDateString()
  warrantyEndDate?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(200)
  warrantyProvider?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsUUID()
  departmentId?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsUUID()
  branchId?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(100)
  building?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(50)
  floor?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(50)
  room?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(300)
  locationNotes?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsIP()
  ipAddress?: string;

  @ApiPropertyOptional({ example: 'AA:BB:CC:DD:EE:FF' })
  @IsOptional()
  @Matches(/^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$/, { message: 'invalid MAC address' })
  macAddress?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(100)
  operatingSystem?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(100)
  cpu?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(50)
  ram?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(50)
  storage?: string;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(2000)
  notes?: string;

  @ApiPropertyOptional({ type: Object })
  @IsOptional()
  @IsObject()
  customFields?: Record<string, unknown>;

  @ApiPropertyOptional({ type: [AssetAttachmentDto] })
  @IsOptional()
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => AssetAttachmentDto)
  attachments?: AssetAttachmentDto[];
}

export class UpdateAssetDto extends PartialType(CreateAssetDto) {}

export class TransitionAssetDto {
  @ApiProperty({ enum: AssetStatus })
  @IsEnum(AssetStatus)
  status: AssetStatus;

  @ApiPropertyOptional()
  @IsOptional()
  @IsString()
  @MaxLength(1000)
  reason?: string;
}

export class AssetFilterDto {
  @ApiPropertyOptional() @IsOptional() @IsString() search?: string;
  @ApiPropertyOptional({ enum: AssetStatus }) @IsOptional() @IsEnum(AssetStatus) status?: AssetStatus;
  @ApiPropertyOptional({ enum: AssetCondition }) @IsOptional() @IsEnum(AssetCondition) condition?: AssetCondition;
  @ApiPropertyOptional() @IsOptional() @IsUUID() categoryId?: string;
  @ApiPropertyOptional() @IsOptional() @IsUUID() branchId?: string;
  @ApiPropertyOptional() @IsOptional() @IsUUID() departmentId?: string;
  @ApiPropertyOptional() @IsOptional() @IsUUID() supplierId?: string;
  @ApiPropertyOptional() @IsOptional() @IsUUID() assignedEmployeeId?: string;
  @ApiPropertyOptional() @IsOptional() @IsString() manufacturer?: string;
  @ApiPropertyOptional({ description: 'Warranty expiring on/before this date' })
  @IsOptional()
  @IsDateString()
  warrantyExpiresBefore?: string;
  @ApiPropertyOptional() @IsOptional() @IsDateString() purchasedAfter?: string;
  @ApiPropertyOptional() @IsOptional() @IsDateString() purchasedBefore?: string;
}
