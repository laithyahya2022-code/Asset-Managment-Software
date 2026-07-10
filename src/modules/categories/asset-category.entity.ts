import { Column, Entity, Index } from 'typeorm';
import { TenantBaseEntity } from '../../common/entities/tenant-base.entity';

export interface CustomFieldDefinition {
  key: string;
  label: string;
  type: 'text' | 'number' | 'date' | 'boolean' | 'select';
  required?: boolean;
  options?: string[];
}

/**
 * Asset type (Laptop, Server, Router…). Tenants define their own catalog;
 * per-category custom fields make any asset type representable without
 * schema changes.
 */
@Entity('asset_categories')
@Index(['organizationId', 'code'], { unique: true })
export class AssetCategory extends TenantBaseEntity {
  @Column({ length: 200 })
  name: string;

  @Column({ length: 30 })
  code: string;

  @Column({ length: 500, nullable: true })
  description?: string;

  /** Default useful life in years, used for straight-line depreciation. */
  @Column({ type: 'int', default: 5 })
  usefulLifeYears: number;

  @Column({ type: 'simple-json', nullable: true })
  customFieldDefinitions?: CustomFieldDefinition[];

  @Column({ default: true })
  isActive: boolean;
}
