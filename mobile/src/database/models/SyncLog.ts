import { Model } from '@nozbe/watermelondb';
import { field, date, readonly, json, Q } from '@nozbe/watermelondb/decorators';

export type SyncType = 'push' | 'pull' | 'full';
export type SyncLogStatus = 'started' | 'completed' | 'failed';

interface SyncError {
  message: string;
  code?: string;
  timestamp: number;
}

export default class SyncLog extends Model {
  static table = 'sync_logs';

  @field('sync_type') syncType!: SyncType;
  @field('status') status!: SyncLogStatus;
  @field('started_at') startedAt!: number;
  @field('completed_at') completedAt?: number;
  @field('records_pushed') recordsPushed!: number;
  @field('records_pulled') recordsPulled!: number;
  @field('conflicts_resolved') conflictsResolved!: number;
  @json('errors', json => json || []) errors!: SyncError[];
  @readonly @date('created_at') createdAt!: Date;
  @readonly @date('updated_at') updatedAt!: Date;

  get duration(): number {
    if (!this.completedAt) return 0;
    return this.completedAt - this.startedAt;
  }

  get durationSeconds(): number {
    return this.duration / 1000;
  }

  get totalRecords(): number {
    return this.recordsPushed + this.recordsPulled;
  }

  get hasErrors(): boolean {
    return this.errors.length > 0;
  }

  get isSuccess(): boolean {
    return this.status === 'completed' && !this.hasErrors;
  }

  static lastSuccessfulSync() {
    return this.query(
      Q.where('status', 'completed'),
      Q.sortBy('completed_at', Q.desc),
      Q.take(1),
    ).fetch();
  }

  static recentSyncs(limit: number = 10) {
    return this.query(
      Q.sortBy('started_at', Q.desc),
      Q.take(limit),
    );
  }
}