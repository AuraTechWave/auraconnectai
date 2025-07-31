import { Model } from '@nozbe/watermelondb';
import { field, date, readonly } from '@nozbe/watermelondb/decorators';

export type SyncStatus = 'pending' | 'syncing' | 'synced' | 'conflict';

export default class BaseModel extends Model {
  @field('server_id') serverId?: string;
  @field('sync_status') syncStatus!: SyncStatus;
  @field('last_modified') lastModified!: number;
  @field('is_deleted') isDeleted!: boolean;
  @readonly @date('created_at') createdAt!: Date;
  @readonly @date('updated_at') updatedAt!: Date;

  // Helper methods
  get isPending(): boolean {
    return this.syncStatus === 'pending';
  }

  get isSynced(): boolean {
    return this.syncStatus === 'synced' && !!this.serverId;
  }

  get hasConflict(): boolean {
    return this.syncStatus === 'conflict';
  }

  async markAsPending() {
    await this.update(record => {
      record.syncStatus = 'pending';
      record.lastModified = Date.now();
    });
  }

  async markAsSyncing() {
    await this.update(record => {
      record.syncStatus = 'syncing';
    });
  }

  async markAsSynced(serverId: string) {
    await this.update(record => {
      record.serverId = serverId;
      record.syncStatus = 'synced';
    });
  }

  async markAsConflict() {
    await this.update(record => {
      record.syncStatus = 'conflict';
    });
  }

  async softDelete() {
    await this.update(record => {
      record.isDeleted = true;
      record.syncStatus = 'pending';
      record.lastModified = Date.now();
    });
  }
}