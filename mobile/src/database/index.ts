import { Database } from '@nozbe/watermelondb';
import SQLiteAdapter from '@nozbe/watermelondb/adapters/sqlite';

import schema from './schema';
import migrations from './migrations';

// Import models
import Order from './models/Order';
import OrderItem from './models/OrderItem';
import Staff from './models/Staff';
import Shift from './models/Shift';
import MenuItem from './models/MenuItem';
import MenuCategory from './models/MenuCategory';
import Customer from './models/Customer';
import SyncLog from './models/SyncLog';

const adapter = new SQLiteAdapter({
  schema,
  migrations,
  jsi: true, // Use JSI for better performance on iOS
  onSetUpError: error => {
    console.error('[Database] Setup error:', error);
  },
});

const database = new Database({
  adapter,
  modelClasses: [
    Order,
    OrderItem,
    Staff,
    Shift,
    MenuItem,
    MenuCategory,
    Customer,
    SyncLog,
  ],
});

export default database;

// Export for type safety
export type DatabaseType = typeof database;
export type Models = typeof database.collections;
