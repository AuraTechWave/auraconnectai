"""Add performance indexes for analytics queries

Revision ID: add_performance_indexes_2025_01_21
Revises: 
Create Date: 2025-01-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_performance_indexes_2025_01_21'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add indexes to improve query performance for analytics operations"""
    
    # Indexes for POS Analytics queries
    # Index for provider summaries query
    op.create_index(
        'idx_pos_analytics_snapshot_provider_date',
        'pos_analytics_snapshot',
        ['provider_id', 'snapshot_date'],
        if_not_exists=True
    )
    
    # Index for terminal health queries
    op.create_index(
        'idx_pos_terminal_health_provider_status',
        'pos_terminal_health',
        ['provider_id', 'health_status'],
        if_not_exists=True
    )
    
    # Index for alerts queries
    op.create_index(
        'idx_pos_analytics_alert_provider_active',
        'pos_analytics_alert',
        ['provider_id', 'is_active'],
        if_not_exists=True
    )
    
    # Indexes for Sales Analytics queries
    # Index for order date range queries
    op.create_index(
        'idx_order_date_status',
        'orders',
        ['order_date', 'status'],
        if_not_exists=True
    )
    
    # Index for order customer queries
    op.create_index(
        'idx_order_customer_date',
        'orders',
        ['customer_id', 'order_date'],
        if_not_exists=True
    )
    
    # Index for order items product queries
    op.create_index(
        'idx_order_item_product_order',
        'order_items',
        ['menu_item_id', 'order_id'],
        if_not_exists=True
    )
    
    # Index for staff performance queries
    op.create_index(
        'idx_order_staff_date',
        'orders',
        ['staff_id', 'created_at'],
        if_not_exists=True
    )
    
    # Index for shift queries
    op.create_index(
        'idx_shift_staff_date_status',
        'shifts',
        ['staff_id', 'date', 'status'],
        if_not_exists=True
    )
    
    # Indexes for AI insights queries
    # Index for hourly order patterns
    op.create_index(
        'idx_order_date_hour',
        'orders',
        [sa.text("DATE(order_date)"), sa.text("EXTRACT(hour FROM order_date)")],
        if_not_exists=True,
        postgresql_using='btree'
    )
    
    # Index for customer analysis
    op.create_index(
        'idx_order_customer_status',
        'orders',
        ['customer_id', 'status'],
        if_not_exists=True
    )
    
    # Indexes for Reservation queries
    # Index for availability checks
    op.create_index(
        'idx_reservation_date_time_status',
        'reservations',
        ['reservation_date', 'reservation_time', 'status'],
        if_not_exists=True
    )
    
    # Index for customer reservation queries
    op.create_index(
        'idx_reservation_customer_date',
        'reservations',
        ['customer_id', 'reservation_date'],
        if_not_exists=True
    )
    
    # Composite indexes for complex queries
    # Index for analytics aggregations by date range and provider
    op.create_index(
        'idx_pos_analytics_composite',
        'pos_analytics_snapshot',
        ['snapshot_date', 'provider_id', 'total_transactions', 'total_transaction_value'],
        if_not_exists=True
    )
    
    # Index for menu item category joins
    op.create_index(
        'idx_menu_item_category',
        'menu_items',
        ['category_id', 'is_active'],
        if_not_exists=True
    )
    
    # Partial indexes for common filters
    # Index for active providers only
    op.create_index(
        'idx_external_pos_provider_active',
        'external_pos_provider',
        ['is_active'],
        if_not_exists=True,
        postgresql_where=sa.text('is_active = true')
    )
    
    # Index for completed orders only
    op.create_index(
        'idx_order_completed',
        'orders',
        ['created_at', 'total_amount'],
        if_not_exists=True,
        postgresql_where=sa.text("status IN ('completed', 'paid')")
    )
    
    # Index for active alerts only
    op.create_index(
        'idx_pos_alert_active_severity',
        'pos_analytics_alert',
        ['severity', 'created_at'],
        if_not_exists=True,
        postgresql_where=sa.text('is_active = true')
    )


def downgrade():
    """Remove performance indexes"""
    
    # Drop all indexes in reverse order
    op.drop_index('idx_pos_alert_active_severity', 'pos_analytics_alert', if_exists=True)
    op.drop_index('idx_order_completed', 'orders', if_exists=True)
    op.drop_index('idx_external_pos_provider_active', 'external_pos_provider', if_exists=True)
    op.drop_index('idx_menu_item_category', 'menu_items', if_exists=True)
    op.drop_index('idx_pos_analytics_composite', 'pos_analytics_snapshot', if_exists=True)
    op.drop_index('idx_reservation_customer_date', 'reservations', if_exists=True)
    op.drop_index('idx_reservation_date_time_status', 'reservations', if_exists=True)
    op.drop_index('idx_order_customer_status', 'orders', if_exists=True)
    op.drop_index('idx_order_date_hour', 'orders', if_exists=True)
    op.drop_index('idx_shift_staff_date_status', 'shifts', if_exists=True)
    op.drop_index('idx_order_staff_date', 'orders', if_exists=True)
    op.drop_index('idx_order_item_product_order', 'order_items', if_exists=True)
    op.drop_index('idx_order_customer_date', 'orders', if_exists=True)
    op.drop_index('idx_order_date_status', 'orders', if_exists=True)
    op.drop_index('idx_pos_analytics_alert_provider_active', 'pos_analytics_alert', if_exists=True)
    op.drop_index('idx_pos_terminal_health_provider_status', 'pos_terminal_health', if_exists=True)
    op.drop_index('idx_pos_analytics_snapshot_provider_date', 'pos_analytics_snapshot', if_exists=True)