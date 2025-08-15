import { appSchema, tableSchema } from '@nozbe/watermelondb';

export default appSchema({
  version: 1,
  tables: [
    tableSchema({
      name: 'orders',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'order_number', type: 'string' },
        { name: 'customer_id', type: 'string', isOptional: true },
        { name: 'staff_id', type: 'string', isOptional: true },
        { name: 'status', type: 'string' },
        { name: 'order_type', type: 'string' },
        { name: 'table_number', type: 'string', isOptional: true },
        { name: 'subtotal', type: 'number' },
        { name: 'tax_amount', type: 'number' },
        { name: 'discount_amount', type: 'number' },
        { name: 'tip_amount', type: 'number' },
        { name: 'total_amount', type: 'number' },
        { name: 'payment_status', type: 'string' },
        { name: 'notes', type: 'string', isOptional: true },
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'order_items',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'order_id', type: 'string', isIndexed: true },
        { name: 'menu_item_id', type: 'string' },
        { name: 'name', type: 'string' },
        { name: 'quantity', type: 'number' },
        { name: 'unit_price', type: 'number' },
        { name: 'total_price', type: 'number' },
        { name: 'modifiers', type: 'string', isOptional: true }, // JSON string
        { name: 'special_instructions', type: 'string', isOptional: true },
        { name: 'status', type: 'string' },
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'staff',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'employee_id', type: 'string', isIndexed: true },
        { name: 'first_name', type: 'string' },
        { name: 'last_name', type: 'string' },
        { name: 'email', type: 'string' },
        { name: 'phone', type: 'string', isOptional: true },
        { name: 'role', type: 'string' },
        { name: 'department', type: 'string', isOptional: true },
        { name: 'is_active', type: 'boolean' },
        { name: 'hire_date', type: 'number', isOptional: true },
        { name: 'hourly_rate', type: 'number', isOptional: true },
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'shifts',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'staff_id', type: 'string', isIndexed: true },
        { name: 'shift_date', type: 'number' },
        { name: 'start_time', type: 'number' },
        { name: 'end_time', type: 'number', isOptional: true },
        { name: 'actual_start', type: 'number', isOptional: true },
        { name: 'actual_end', type: 'number', isOptional: true },
        { name: 'break_duration', type: 'number' },
        { name: 'status', type: 'string' },
        { name: 'notes', type: 'string', isOptional: true },
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'menu_items',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'category_id', type: 'string', isIndexed: true },
        { name: 'name', type: 'string' },
        { name: 'description', type: 'string', isOptional: true },
        { name: 'price', type: 'number' },
        { name: 'cost', type: 'number', isOptional: true },
        { name: 'image_url', type: 'string', isOptional: true },
        { name: 'is_available', type: 'boolean' },
        { name: 'preparation_time', type: 'number', isOptional: true },
        { name: 'tags', type: 'string', isOptional: true }, // JSON array
        { name: 'modifiers', type: 'string', isOptional: true }, // JSON array
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'menu_categories',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'name', type: 'string' },
        { name: 'description', type: 'string', isOptional: true },
        { name: 'display_order', type: 'number' },
        { name: 'is_active', type: 'boolean' },
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'customers',
      columns: [
        { name: 'server_id', type: 'string', isOptional: true },
        { name: 'first_name', type: 'string' },
        { name: 'last_name', type: 'string' },
        { name: 'email', type: 'string', isOptional: true },
        { name: 'phone', type: 'string', isOptional: true },
        { name: 'loyalty_points', type: 'number' },
        { name: 'preferences', type: 'string', isOptional: true }, // JSON
        { name: 'notes', type: 'string', isOptional: true },
        { name: 'sync_status', type: 'string' },
        { name: 'last_modified', type: 'number' },
        { name: 'is_deleted', type: 'boolean' },
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),

    tableSchema({
      name: 'sync_logs',
      columns: [
        { name: 'sync_type', type: 'string' }, // push, pull, full
        { name: 'status', type: 'string' }, // started, completed, failed
        { name: 'started_at', type: 'number' },
        { name: 'completed_at', type: 'number', isOptional: true },
        { name: 'records_pushed', type: 'number' },
        { name: 'records_pulled', type: 'number' },
        { name: 'conflicts_resolved', type: 'number' },
        { name: 'errors', type: 'string', isOptional: true }, // JSON array
        { name: 'created_at', type: 'number' },
        { name: 'updated_at', type: 'number' },
      ],
    }),
  ],
});
