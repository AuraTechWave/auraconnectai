import { field, children, writer, Q } from '@nozbe/watermelondb/decorators';
import BaseModel from './BaseModel';

export type StaffRole =
  | 'admin'
  | 'manager'
  | 'server'
  | 'chef'
  | 'cashier'
  | 'host';
export type Department = 'front_of_house' | 'kitchen' | 'management' | 'bar';

export default class Staff extends BaseModel {
  static table = 'staff';
  static associations = {
    shifts: { type: 'has_many', foreignKey: 'staff_id' },
    orders: { type: 'has_many', foreignKey: 'staff_id' },
  } as const;

  @field('employee_id') employeeId!: string;
  @field('first_name') firstName!: string;
  @field('last_name') lastName!: string;
  @field('email') email!: string;
  @field('phone') phone?: string;
  @field('role') role!: StaffRole;
  @field('department') department?: Department;
  @field('is_active') isActive!: boolean;
  @field('hire_date') hireDate?: number;
  @field('hourly_rate') hourlyRate?: number;

  @children('shifts') shifts!: any;
  @children('orders') orders!: any;

  get fullName(): string {
    return `${this.firstName} ${this.lastName}`;
  }

  get isManager(): boolean {
    return ['admin', 'manager'].includes(this.role);
  }

  @writer async clockIn() {
    const { shifts } = this.collections.get('shifts');
    const now = Date.now();

    await shifts.create(shift => {
      shift.staffId = this.id;
      shift.shiftDate = now;
      shift.startTime = now;
      shift.actualStart = now;
      shift.status = 'active';
      shift.syncStatus = 'pending';
      shift.lastModified = now;
    });
  }

  async getCurrentShift() {
    const shifts = await this.shifts.fetch();
    return shifts.find(shift => shift.status === 'active');
  }

  static activeStaff() {
    return this.query(
      Q.where('is_active', true),
      Q.where('is_deleted', false),
      Q.sortBy('first_name', Q.asc),
    );
  }

  static byRole(role: StaffRole) {
    return this.query(
      Q.where('role', role),
      Q.where('is_active', true),
      Q.where('is_deleted', false),
    );
  }
}
