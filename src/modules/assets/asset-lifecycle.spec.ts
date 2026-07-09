import { BadRequestException } from '@nestjs/common';
import { assertTransition, AssetStatus } from './asset-lifecycle';

describe('Asset lifecycle state machine', () => {
  it('allows the canonical procurement path', () => {
    const path: AssetStatus[] = [
      AssetStatus.PLANNED,
      AssetStatus.PURCHASE_REQUESTED,
      AssetStatus.APPROVED,
      AssetStatus.ORDERED,
      AssetStatus.RECEIVED,
      AssetStatus.IN_STOCK,
      AssetStatus.DEPLOYED,
      AssetStatus.IN_MAINTENANCE,
      AssetStatus.IN_STOCK,
      AssetStatus.RETIRED,
      AssetStatus.DISPOSED,
    ];
    for (let i = 0; i < path.length - 1; i++) {
      expect(() => assertTransition(path[i], path[i + 1])).not.toThrow();
    }
  });

  it('rejects skipping procurement stages', () => {
    expect(() => assertTransition(AssetStatus.PLANNED, AssetStatus.DEPLOYED)).toThrow(
      BadRequestException,
    );
    expect(() => assertTransition(AssetStatus.ORDERED, AssetStatus.IN_STOCK)).toThrow(
      BadRequestException,
    );
  });

  it('treats DISPOSED as terminal', () => {
    for (const status of Object.values(AssetStatus)) {
      expect(() => assertTransition(AssetStatus.DISPOSED, status)).toThrow(BadRequestException);
    }
  });

  it('allows recovering a LOST asset', () => {
    expect(() => assertTransition(AssetStatus.LOST, AssetStatus.IN_STOCK)).not.toThrow();
  });
});
