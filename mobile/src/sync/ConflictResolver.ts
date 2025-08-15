import { Q } from '@nozbe/watermelondb';
import database from '@database/index';
import { logger } from '@utils/logger';
import { showToast } from '@utils/toast';

export interface ConflictInfo {
  collection: string;
  localId: string;
  serverId?: string;
  localData: any;
  serverData: any;
  type: 'create' | 'update' | 'delete';
  strategy?:
    | 'server_wins'
    | 'client_wins'
    | 'last_write_wins'
    | 'merge'
    | 'manual';
  manualResolution?: any;
}

export interface ConflictResult {
  resolved: any;
  conflicts: ConflictInfo[];
}

export class ConflictResolver {
  private defaultStrategy:
    | 'server_wins'
    | 'client_wins'
    | 'last_write_wins'
    | 'merge' = 'last_write_wins';

  async detectConflicts(changes: any): Promise<ConflictResult> {
    const conflicts: ConflictInfo[] = [];
    const resolved: any = {};

    for (const [collection, data] of Object.entries(changes)) {
      resolved[collection] = {
        created: [],
        updated: [],
        deleted: [],
      };

      // Check for conflicts in updates
      if (data.updated) {
        for (const serverRecord of data.updated) {
          const conflict = await this.checkUpdateConflict(
            collection,
            serverRecord,
          );
          if (conflict) {
            conflicts.push(conflict);
            // Apply default resolution strategy
            const resolvedData = await this.resolveConflict(conflict);
            resolved[collection].updated.push(resolvedData);
          } else {
            resolved[collection].updated.push(serverRecord);
          }
        }
      }

      // Check for conflicts in deletes
      if (data.deleted) {
        for (const serverId of data.deleted) {
          const conflict = await this.checkDeleteConflict(collection, serverId);
          if (conflict) {
            conflicts.push(conflict);
            // Apply default resolution strategy
            const shouldDelete = await this.resolveDeleteConflict(conflict);
            if (shouldDelete) {
              resolved[collection].deleted.push(serverId);
            }
          } else {
            resolved[collection].deleted.push(serverId);
          }
        }
      }

      // Creates typically don't have conflicts
      resolved[collection].created = data.created || [];
    }

    return { resolved, conflicts };
  }

  async resolveConflicts(conflicts: ConflictInfo[]): Promise<void> {
    for (const conflict of conflicts) {
      try {
        await this.resolveConflict(conflict);
      } catch (error) {
        logger.error('Failed to resolve conflict', { conflict, error });
      }
    }
  }

  private async checkUpdateConflict(
    collection: string,
    serverRecord: any,
  ): Promise<ConflictInfo | null> {
    try {
      const dbCollection = database.collections.get(collection);
      const localRecord = await dbCollection.find(
        serverRecord.localId || serverRecord.id,
      );

      if (!localRecord) {
        return null;
      }

      // Check if local record has been modified since last sync
      if (
        localRecord.syncStatus === 'pending' ||
        localRecord.syncStatus === 'conflict'
      ) {
        const localData = this.extractRecordData(localRecord);
        return {
          collection,
          localId: localRecord.id,
          serverId: serverRecord.id,
          localData,
          serverData: serverRecord,
          type: 'update',
          strategy: this.defaultStrategy,
        };
      }
    } catch (error) {
      logger.warn('Error checking update conflict', { collection, error });
    }

    return null;
  }

  private async checkDeleteConflict(
    collection: string,
    serverId: string,
  ): Promise<ConflictInfo | null> {
    try {
      const dbCollection = database.collections.get(collection);
      const localRecords = await dbCollection
        .query(
          Q.where('server_id', serverId),
          Q.where('sync_status', Q.oneOf(['pending', 'conflict'])),
        )
        .fetch();

      if (localRecords.length > 0) {
        const localRecord = localRecords[0];
        const localData = this.extractRecordData(localRecord);
        return {
          collection,
          localId: localRecord.id,
          serverId,
          localData,
          serverData: null,
          type: 'delete',
          strategy: this.defaultStrategy,
        };
      }
    } catch (error) {
      logger.warn('Error checking delete conflict', { collection, error });
    }

    return null;
  }

  private async resolveConflict(conflict: ConflictInfo): Promise<any> {
    const strategy = conflict.strategy || this.defaultStrategy;

    switch (strategy) {
      case 'server_wins':
        return conflict.serverData;

      case 'client_wins':
        return conflict.localData;

      case 'last_write_wins':
        return this.resolveByTimestamp(conflict);

      case 'merge':
        return this.mergeConflict(conflict);

      case 'manual':
        return conflict.manualResolution || conflict.serverData;

      default:
        return conflict.serverData;
    }
  }

  private async resolveDeleteConflict(
    conflict: ConflictInfo,
  ): Promise<boolean> {
    const strategy = conflict.strategy || this.defaultStrategy;

    switch (strategy) {
      case 'server_wins':
        return true; // Delete the record

      case 'client_wins':
        return false; // Keep the record

      case 'last_write_wins':
        // If local record was modified after server deletion, keep it
        return conflict.localData.lastModified < Date.now() - 300000; // 5 minutes

      default:
        return true;
    }
  }

  private resolveByTimestamp(conflict: ConflictInfo): any {
    const localTimestamp = conflict.localData.lastModified || 0;
    const serverTimestamp =
      conflict.serverData.lastModified || conflict.serverData.updated_at || 0;

    if (localTimestamp > serverTimestamp) {
      logger.debug('Conflict resolved: client wins by timestamp', { conflict });
      return conflict.localData;
    } else {
      logger.debug('Conflict resolved: server wins by timestamp', { conflict });
      return conflict.serverData;
    }
  }

  private mergeConflict(conflict: ConflictInfo): any {
    // Collection-specific merge strategies
    switch (conflict.collection) {
      case 'orders':
        return this.mergeOrder(conflict);

      case 'menu_items':
        return this.mergeMenuItem(conflict);

      case 'customers':
        return this.mergeCustomer(conflict);

      default:
        // Default merge: combine fields, preferring non-null values
        return this.defaultMerge(conflict);
    }
  }

  private mergeOrder(conflict: ConflictInfo): any {
    const { localData, serverData } = conflict;

    // For orders, server status takes precedence
    return {
      ...localData,
      ...serverData,
      status: serverData.status,
      // Preserve local notes if they're newer
      notes:
        localData.lastModified > serverData.updated_at
          ? localData.notes
          : serverData.notes,
      // Merge items if both have changes
      items: this.mergeOrderItems(localData.items, serverData.items),
    };
  }

  private mergeMenuItem(conflict: ConflictInfo): any {
    const { localData, serverData } = conflict;

    // For menu items, server price and availability take precedence
    return {
      ...localData,
      ...serverData,
      price: serverData.price,
      isAvailable: serverData.isAvailable,
      // Keep local customizations if any
      customizations: localData.customizations || serverData.customizations,
    };
  }

  private mergeCustomer(conflict: ConflictInfo): any {
    const { localData, serverData } = conflict;

    // Merge customer preferences
    return {
      ...serverData,
      // Merge preferences
      preferences: {
        ...serverData.preferences,
        ...localData.preferences,
      },
      // Server loyalty points are authoritative
      loyaltyPoints: serverData.loyaltyPoints,
      // Keep the most recent notes
      notes:
        localData.lastModified > serverData.updated_at
          ? localData.notes
          : serverData.notes,
    };
  }

  private defaultMerge(conflict: ConflictInfo): any {
    const { localData, serverData } = conflict;
    const merged = { ...serverData };

    // Prefer non-null/non-empty values
    for (const key in localData) {
      if (
        localData[key] !== null &&
        localData[key] !== undefined &&
        localData[key] !== ''
      ) {
        if (
          !serverData[key] ||
          serverData[key] === null ||
          serverData[key] === ''
        ) {
          merged[key] = localData[key];
        }
      }
    }

    return merged;
  }

  private mergeOrderItems(localItems: any[], serverItems: any[]): any[] {
    // This is a simplified merge - in production, you'd want more sophisticated logic
    const itemMap = new Map();

    // Add server items first
    serverItems?.forEach(item => {
      itemMap.set(item.menuItemId || item.menu_item_id, item);
    });

    // Override with local items if they exist
    localItems?.forEach(item => {
      const key = item.menuItemId || item.menu_item_id;
      if (itemMap.has(key)) {
        // Merge quantities
        const serverItem = itemMap.get(key);
        itemMap.set(key, {
          ...serverItem,
          ...item,
          quantity: Math.max(item.quantity, serverItem.quantity),
        });
      } else {
        itemMap.set(key, item);
      }
    });

    return Array.from(itemMap.values());
  }

  private extractRecordData(record: any): any {
    const data = { ...record._raw };
    delete data._status;
    delete data._changed;
    return data;
  }

  setDefaultStrategy(
    strategy: 'server_wins' | 'client_wins' | 'last_write_wins' | 'merge',
  ) {
    this.defaultStrategy = strategy;
  }

  async showConflictSummary(conflicts: ConflictInfo[]) {
    if (conflicts.length === 0) return;

    const summary = conflicts.reduce(
      (acc, conflict) => {
        acc[conflict.collection] = (acc[conflict.collection] || 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

    const message = Object.entries(summary)
      .map(([collection, count]) => `${collection}: ${count}`)
      .join(', ');

    showToast('warning', 'Sync Conflicts Resolved', message);
  }
}
