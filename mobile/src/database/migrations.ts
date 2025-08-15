import {
  schemaMigrations,
  createTable,
  addColumns,
} from '@nozbe/watermelondb/Schema/migrations';

export default schemaMigrations({
  migrations: [
    // Initial schema is version 1, so no migrations needed yet
    // Future migrations would go here when schema changes
    // Example:
    // {
    //   toVersion: 2,
    //   steps: [
    //     addColumns({
    //       table: 'orders',
    //       columns: [
    //         { name: 'delivery_address', type: 'string', isOptional: true },
    //       ],
    //     }),
    //   ],
    // },
  ],
});
