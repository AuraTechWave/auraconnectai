import { field, relation, writer } from '@nozbe/watermelondb/decorators';
import BaseModel from './BaseModel';

export type ShiftStatus = 'scheduled' | 'active' | 'completed' | 'cancelled';

export default class Shift extends BaseModel {
  static table = 'shifts';
  static associations = {
    staff: { type: 'belongs_to', key: 'staff_id' },
  } as const;

  @field('staff_id') staffId!: string;
  @field('shift_date') shiftDate!: number;
  @field('start_time') startTime!: number;
  @field('end_time') endTime?: number;
  @field('actual_start') actualStart?: number;
  @field('actual_end') actualEnd?: number;
  @field('break_duration') breakDuration!: number;
  @field('status') status!: ShiftStatus;
  @field('notes') notes?: string;

  @relation('staff', 'staff_id') staff!: any;

  get duration(): number {
    if (!this.actualEnd || !this.actualStart) return 0;
    return this.actualEnd - this.actualStart - this.breakDuration;
  }

  get hoursWorked(): number {
    return this.duration / (1000 * 60 * 60); // Convert to hours
  }

  get isActive(): boolean {
    return this.status === 'active';
  }

  get isLate(): boolean {
    if (!this.actualStart) return false;
    return this.actualStart > this.startTime + 15 * 60 * 1000; // 15 minutes grace
  }

  @writer async clockOut(notes?: string) {
    const now = Date.now();
    await this.update(shift => {
      shift.actualEnd = now;
      shift.endTime = now;
      shift.status = 'completed';
      shift.notes = notes;
      shift.syncStatus = 'pending';
      shift.lastModified = now;
    });
  }

  @writer async addBreak(minutes: number) {
    await this.update(shift => {
      shift.breakDuration += minutes * 60 * 1000;
      shift.syncStatus = 'pending';
      shift.lastModified = Date.now();
    });
  }
}
