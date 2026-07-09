import { Column, Entity, Index } from 'typeorm';
import { BaseEntity } from '../../common/entities/base.entity';

/**
 * A tenant. Every other business row carries this entity's id as its
 * isolation discriminator.
 */
@Entity('organizations')
export class Organization extends BaseEntity {
  @Column({ length: 200 })
  name: string;

  @Index({ unique: true })
  @Column({ length: 100 })
  slug: string;

  @Column({ length: 320, nullable: true })
  contactEmail?: string;

  @Column({ length: 100, nullable: true })
  country?: string;

  @Column({ length: 10, default: 'USD' })
  currency: string;

  /** Tenant-level preferences: branding, tag prefix, notification windows… */
  @Column({ type: 'simple-json', nullable: true })
  settings?: {
    brandColor?: string;
    logoUrl?: string;
    assetTagPrefix?: string;
    warrantyAlertDays?: number[];
    licenseAlertDays?: number[];
  };

  @Column({ default: true })
  isActive: boolean;
}
