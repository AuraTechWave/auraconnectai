"""Merge all migration heads

Revision ID: merge_all_heads
Revises: 0005_add_priority_fields_to_orders, 20250730_1000, 0005_add_print_ticket_tables, 0005_add_payment_reconciliation, 006_add_rewards_engine, 20250725_0454_0005, 20250731_1000_add_external_pos_webhook_tables, 20250725_2126_0009, recipe_performance_indexes, 0003_create_tax_tables, update_inventory_adjustments, 0016, 9a7b19d94ae6, add_enhanced_reservation_system, 008_pos_analytics, add_manual_review_tables
Create Date: 2025-08-09 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_all_heads'
down_revision = (
    '0005_add_priority_fields_to_orders',
    '20250730_1000', 
    '0005_add_print_ticket_tables',
    '0005_add_payment_reconciliation',
    '006_add_rewards_engine',
    '20250725_0454_0005',
    '20250731_1000_add_external_pos_webhook_tables',
    '20250725_2126_0009',
    'recipe_performance_indexes',
    '0003_create_tax_tables',
    'update_inventory_adjustments',
    '0016',
    '9a7b19d94ae6',
    'add_enhanced_reservation_system',
    '008_pos_analytics',
    'add_manual_review_tables'
)
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration, no operations needed
    pass


def downgrade():
    # This is a merge migration, no operations needed
    pass