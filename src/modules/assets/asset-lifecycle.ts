import { BadRequestException } from '@nestjs/common';

/**
 * Asset lifecycle:
 * Planning → Purchase Request → Approval → Procurement → Receiving →
 * Inventory → Deployment → Assignment ⇄ Maintenance/Repair/Transfer →
 * Audit → Retirement → Disposal.
 */
export enum AssetStatus {
  PLANNED = 'PLANNED',
  PURCHASE_REQUESTED = 'PURCHASE_REQUESTED',
  APPROVED = 'APPROVED',
  ORDERED = 'ORDERED',
  RECEIVED = 'RECEIVED',
  IN_STOCK = 'IN_STOCK',
  DEPLOYED = 'DEPLOYED',
  ASSIGNED = 'ASSIGNED',
  IN_MAINTENANCE = 'IN_MAINTENANCE',
  IN_REPAIR = 'IN_REPAIR',
  IN_TRANSFER = 'IN_TRANSFER',
  RETIRED = 'RETIRED',
  DISPOSED = 'DISPOSED',
  LOST = 'LOST',
}

export enum AssetCondition {
  NEW = 'NEW',
  EXCELLENT = 'EXCELLENT',
  GOOD = 'GOOD',
  FAIR = 'FAIR',
  POOR = 'POOR',
  DAMAGED = 'DAMAGED',
  FOR_PARTS = 'FOR_PARTS',
}

/** Statuses in which an asset can be checked out to an employee. */
export const CHECKOUTABLE_STATUSES = [AssetStatus.IN_STOCK, AssetStatus.DEPLOYED];

const TRANSITIONS: Record<AssetStatus, AssetStatus[]> = {
  [AssetStatus.PLANNED]: [AssetStatus.PURCHASE_REQUESTED],
  [AssetStatus.PURCHASE_REQUESTED]: [AssetStatus.APPROVED, AssetStatus.PLANNED],
  [AssetStatus.APPROVED]: [AssetStatus.ORDERED, AssetStatus.PLANNED],
  [AssetStatus.ORDERED]: [AssetStatus.RECEIVED],
  [AssetStatus.RECEIVED]: [AssetStatus.IN_STOCK],
  [AssetStatus.IN_STOCK]: [
    AssetStatus.DEPLOYED,
    AssetStatus.ASSIGNED,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.IN_REPAIR,
    AssetStatus.IN_TRANSFER,
    AssetStatus.RETIRED,
    AssetStatus.LOST,
  ],
  [AssetStatus.DEPLOYED]: [
    AssetStatus.ASSIGNED,
    AssetStatus.IN_STOCK,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.IN_REPAIR,
    AssetStatus.IN_TRANSFER,
    AssetStatus.RETIRED,
    AssetStatus.LOST,
  ],
  [AssetStatus.ASSIGNED]: [
    AssetStatus.IN_STOCK,
    AssetStatus.DEPLOYED,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.IN_REPAIR,
    AssetStatus.IN_TRANSFER,
    AssetStatus.LOST,
  ],
  [AssetStatus.IN_MAINTENANCE]: [
    AssetStatus.IN_STOCK,
    AssetStatus.DEPLOYED,
    AssetStatus.ASSIGNED,
    AssetStatus.IN_REPAIR,
    AssetStatus.RETIRED,
  ],
  [AssetStatus.IN_REPAIR]: [
    AssetStatus.IN_STOCK,
    AssetStatus.DEPLOYED,
    AssetStatus.ASSIGNED,
    AssetStatus.IN_MAINTENANCE,
    AssetStatus.RETIRED,
  ],
  [AssetStatus.IN_TRANSFER]: [AssetStatus.IN_STOCK, AssetStatus.DEPLOYED, AssetStatus.ASSIGNED],
  [AssetStatus.RETIRED]: [AssetStatus.DISPOSED, AssetStatus.IN_STOCK],
  [AssetStatus.DISPOSED]: [],
  [AssetStatus.LOST]: [AssetStatus.IN_STOCK],
};

export const assertTransition = (from: AssetStatus, to: AssetStatus): void => {
  if (!TRANSITIONS[from]?.includes(to)) {
    throw new BadRequestException(
      `Illegal lifecycle transition ${from} → ${to}. Allowed: ${TRANSITIONS[from]?.join(', ') || 'none'}`,
    );
  }
};
