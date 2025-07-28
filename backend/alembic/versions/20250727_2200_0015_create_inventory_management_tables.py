"""Create inventory management tables with alerts and tracking

Revision ID: 20250727_2200_0015
Revises: 20250727_2100_0014
Create Date: 2025-07-27 22:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250727_2200_0015'
down_revision = '20250727_2100_0014'
branch_labels = None
depends_on = None


def upgrade():
    # Create vendors table
    op.create_table('vendors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('contact_person', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('address_line1', sa.String(length=200), nullable=True),
        sa.Column('address_line2', sa.String(length=200), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('state', sa.String(length=50), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=True),
        sa.Column('country', sa.String(length=100), nullable=True),
        sa.Column('tax_id', sa.String(length=50), nullable=True),
        sa.Column('payment_terms', sa.String(length=100), nullable=True),
        sa.Column('delivery_lead_time', sa.Integer(), nullable=True),
        sa.Column('minimum_order_amount', sa.Float(), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'suspended', 'pending_approval', name='vendorstatus'), nullable=False, server_default='active'),
        sa.Column('rating', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vendors_id'), 'vendors', ['id'], unique=False)
    op.create_index(op.f('ix_vendors_name'), 'vendors', ['name'], unique=False)

    # Create inventory_alerts table
    op.create_table('inventory_alerts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.Enum('low', 'medium', 'high', 'critical', name='alertpriority'), nullable=False, server_default='medium'),
        sa.Column('status', sa.Enum('pending', 'acknowledged', 'resolved', 'dismissed', name='alertstatus'), nullable=False, server_default='pending'),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=True),
        sa.Column('current_value', sa.Float(), nullable=True),
        sa.Column('acknowledged_by', sa.Integer(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('auto_resolve', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_alerts_id'), 'inventory_alerts', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_alerts_alert_type'), 'inventory_alerts', ['alert_type'], unique=False)
    op.create_index('idx_alerts_status_priority', 'inventory_alerts', ['status', 'priority'])

    # Create inventory_adjustments table
    op.create_table('inventory_adjustments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('adjustment_type', sa.Enum('purchase', 'sale', 'waste', 'transfer', 'correction', 'expired', 'damaged', 'recount', name='adjustmenttype'), nullable=False),
        sa.Column('quantity_before', sa.Float(), nullable=False),
        sa.Column('quantity_adjusted', sa.Float(), nullable=False),
        sa.Column('quantity_after', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('reference_type', sa.String(length=50), nullable=True),
        sa.Column('reference_id', sa.String(length=100), nullable=True),
        sa.Column('batch_number', sa.String(length=100), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('reason', sa.String(length=500), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approval_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_adjustments_id'), 'inventory_adjustments', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_adjustments_adjustment_type'), 'inventory_adjustments', ['adjustment_type'], unique=False)

    # Create purchase_orders table
    op.create_table('purchase_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('po_number', sa.String(length=50), nullable=False),
        sa.Column('vendor_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('order_date', sa.DateTime(), nullable=False),
        sa.Column('expected_delivery_date', sa.DateTime(), nullable=True),
        sa.Column('actual_delivery_date', sa.DateTime(), nullable=True),
        sa.Column('subtotal', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('tax_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('shipping_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('total_amount', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('delivery_address', sa.Text(), nullable=True),
        sa.Column('delivery_instructions', sa.Text(), nullable=True),
        sa.Column('tracking_number', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('internal_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['vendor_id'], ['vendors.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_orders_id'), 'purchase_orders', ['id'], unique=False)
    op.create_index(op.f('ix_purchase_orders_po_number'), 'purchase_orders', ['po_number'], unique=True)

    # Create purchase_order_items table
    op.create_table('purchase_order_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('purchase_order_id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('quantity_ordered', sa.Float(), nullable=False),
        sa.Column('quantity_received', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=False),
        sa.Column('total_cost', sa.Float(), nullable=False),
        sa.Column('quality_rating', sa.Integer(), nullable=True),
        sa.Column('condition_notes', sa.Text(), nullable=True),
        sa.Column('batch_number', sa.String(length=100), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ),
        sa.ForeignKeyConstraint(['purchase_order_id'], ['purchase_orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_purchase_order_items_id'), 'purchase_order_items', ['id'], unique=False)

    # Create inventory_usage_logs table
    op.create_table('inventory_usage_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('menu_item_id', sa.Integer(), nullable=True),
        sa.Column('quantity_used', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('order_item_id', sa.Integer(), nullable=True),
        sa.Column('order_date', sa.DateTime(), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('total_cost', sa.Float(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('station', sa.String(length=50), nullable=True),
        sa.Column('shift', sa.String(length=20), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ),
        sa.ForeignKeyConstraint(['menu_item_id'], ['menu_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_usage_logs_id'), 'inventory_usage_logs', ['id'], unique=False)

    # Create inventory_counts table
    op.create_table('inventory_counts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('count_number', sa.String(length=50), nullable=False),
        sa.Column('count_type', sa.String(length=20), nullable=False),
        sa.Column('count_date', sa.DateTime(), nullable=False),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='in_progress'),
        sa.Column('total_items_counted', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_discrepancies', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_value_variance', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('counted_by', sa.Integer(), nullable=False),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('discrepancy_notes', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_counts_id'), 'inventory_counts', ['id'], unique=False)
    op.create_index(op.f('ix_inventory_counts_count_number'), 'inventory_counts', ['count_number'], unique=True)

    # Create inventory_count_items table
    op.create_table('inventory_count_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('inventory_count_id', sa.Integer(), nullable=False),
        sa.Column('inventory_id', sa.Integer(), nullable=False),
        sa.Column('system_quantity', sa.Float(), nullable=False),
        sa.Column('counted_quantity', sa.Float(), nullable=False),
        sa.Column('variance', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('unit_cost', sa.Float(), nullable=True),
        sa.Column('variance_value', sa.Float(), nullable=True),
        sa.Column('batch_number', sa.String(length=100), nullable=True),
        sa.Column('expiration_date', sa.DateTime(), nullable=True),
        sa.Column('location', sa.String(length=100), nullable=True),
        sa.Column('condition', sa.String(length=50), nullable=True),
        sa.Column('counted_by', sa.Integer(), nullable=False),
        sa.Column('verified_by', sa.Integer(), nullable=True),
        sa.Column('count_timestamp', sa.DateTime(), nullable=False),
        sa.Column('adjustment_created', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('adjustment_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['adjustment_id'], ['inventory_adjustments.id'], ),
        sa.ForeignKeyConstraint(['inventory_count_id'], ['inventory_counts.id'], ),
        sa.ForeignKeyConstraint(['inventory_id'], ['inventory.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_count_items_id'), 'inventory_count_items', ['id'], unique=False)

    # Enhance existing inventory table
    op.add_column('inventory', sa.Column('category', sa.String(length=100), nullable=True))
    op.add_column('inventory', sa.Column('max_quantity', sa.Float(), nullable=True))
    op.add_column('inventory', sa.Column('average_cost', sa.Float(), nullable=True))
    op.add_column('inventory', sa.Column('lead_time_days', sa.Integer(), nullable=True))
    op.add_column('inventory', sa.Column('storage_temperature', sa.String(length=50), nullable=True))
    op.add_column('inventory', sa.Column('shelf_life_days', sa.Integer(), nullable=True))
    op.add_column('inventory', sa.Column('track_expiration', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('inventory', sa.Column('track_batches', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('inventory', sa.Column('perishable', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('inventory', sa.Column('enable_low_stock_alerts', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('inventory', sa.Column('alert_threshold_percentage', sa.Float(), nullable=True))
    op.add_column('inventory', sa.Column('last_counted_at', sa.DateTime(), nullable=True))
    
    # Add foreign key to vendors table
    op.add_foreign_key('fk_inventory_vendor', 'inventory', 'vendors', ['vendor_id'], ['id'])
    
    # Create indexes for enhanced inventory table
    op.create_index('idx_inventory_category', 'inventory', ['category'])
    op.create_index('idx_inventory_low_stock', 'inventory', ['quantity', 'threshold'])
    op.create_index('idx_inventory_vendor', 'inventory', ['vendor_id'])

    # Create additional performance indexes
    op.create_index('idx_usage_logs_date_inventory', 'inventory_usage_logs', ['order_date', 'inventory_id'])
    op.create_index('idx_adjustments_date_type', 'inventory_adjustments', ['created_at', 'adjustment_type'])
    op.create_index('idx_alerts_inventory_status', 'inventory_alerts', ['inventory_id', 'status'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_alerts_inventory_status', table_name='inventory_alerts')
    op.drop_index('idx_adjustments_date_type', table_name='inventory_adjustments')
    op.drop_index('idx_usage_logs_date_inventory', table_name='inventory_usage_logs')
    op.drop_index('idx_inventory_vendor', table_name='inventory')
    op.drop_index('idx_inventory_low_stock', table_name='inventory')
    op.drop_index('idx_inventory_category', table_name='inventory')
    op.drop_index('idx_alerts_status_priority', table_name='inventory_alerts')

    # Remove foreign key constraint
    op.drop_constraint('fk_inventory_vendor', 'inventory', type_='foreignkey')

    # Remove columns from inventory table
    op.drop_column('inventory', 'last_counted_at')
    op.drop_column('inventory', 'alert_threshold_percentage')
    op.drop_column('inventory', 'enable_low_stock_alerts')
    op.drop_column('inventory', 'perishable')
    op.drop_column('inventory', 'track_batches')
    op.drop_column('inventory', 'track_expiration')
    op.drop_column('inventory', 'shelf_life_days')
    op.drop_column('inventory', 'storage_temperature')
    op.drop_column('inventory', 'lead_time_days')
    op.drop_column('inventory', 'average_cost')
    op.drop_column('inventory', 'max_quantity')
    op.drop_column('inventory', 'category')

    # Drop new tables
    op.drop_table('inventory_count_items')
    op.drop_table('inventory_counts')
    op.drop_table('inventory_usage_logs')
    op.drop_table('purchase_order_items')
    op.drop_table('purchase_orders')
    op.drop_table('inventory_adjustments')
    op.drop_table('inventory_alerts')
    op.drop_table('vendors')