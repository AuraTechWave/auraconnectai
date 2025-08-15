import {
  field,
  children,
  json,
  writer,
  Q,
} from '@nozbe/watermelondb/decorators';
import BaseModel from './BaseModel';

interface CustomerPreferences {
  dietary?: string[];
  allergies?: string[];
  favoriteItems?: string[];
  specialRequests?: string;
}

export default class Customer extends BaseModel {
  static table = 'customers';
  static associations = {
    orders: { type: 'has_many', foreignKey: 'customer_id' },
  } as const;

  @field('first_name') firstName!: string;
  @field('last_name') lastName!: string;
  @field('email') email?: string;
  @field('phone') phone?: string;
  @field('loyalty_points') loyaltyPoints!: number;
  @json('preferences', json => json || {}) preferences!: CustomerPreferences;
  @field('notes') notes?: string;

  @children('orders') orders!: any;

  get fullName(): string {
    return `${this.firstName} ${this.lastName}`;
  }

  get displayName(): string {
    if (this.email) return this.email;
    if (this.phone) return this.phone;
    return this.fullName;
  }

  @writer async addLoyaltyPoints(points: number) {
    await this.update(customer => {
      customer.loyaltyPoints += points;
      customer.syncStatus = 'pending';
      customer.lastModified = Date.now();
    });
  }

  @writer async updatePreferences(
    newPreferences: Partial<CustomerPreferences>,
  ) {
    await this.update(customer => {
      customer.preferences = { ...customer.preferences, ...newPreferences };
      customer.syncStatus = 'pending';
      customer.lastModified = Date.now();
    });
  }

  static search(term: string) {
    const searchTerm = Q.sanitizeLikeString(term);
    return this.query(
      Q.or(
        Q.where('first_name', Q.like(`%${searchTerm}%`)),
        Q.where('last_name', Q.like(`%${searchTerm}%`)),
        Q.where('email', Q.like(`%${searchTerm}%`)),
        Q.where('phone', Q.like(`%${searchTerm}%`)),
      ),
      Q.where('is_deleted', false),
    );
  }

  static topCustomers(limit = 10) {
    return this.query(
      Q.where('is_deleted', false),
      Q.sortBy('loyalty_points', Q.desc),
      Q.take(limit),
    );
  }
}
