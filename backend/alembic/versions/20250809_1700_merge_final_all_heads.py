"""Merge all remaining migration heads

Revision ID: merge_final_all_heads
Revises: merge_all_heads_v2, merge_final_heads, 0003_create_tax_tables, 0005_add_payment_reconciliation, 0005_add_print_ticket_tables, 0005_add_priority_fields_to_orders, 20250728_0130_0016, 006_add_rewards_engine, 008_pos_analytics, 20250725_0454_0005, 20250725_2126_0009, 20250730_1000, 20250731_1000_add_external_pos_webhook_tables, 9a7b19d94ae6, add_enhanced_reservation_system, add_manual_review_tables_v2, recipe_performance_indexes, update_inventory_adjustments
Create Date: 2025-08-09 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'merge_final_all_heads'
down_revision = (
    'merge_all_heads_v2',
    'merge_final_heads',
    '0003_create_tax_tables',
    '0005_add_payment_reconciliation',
    '0005_add_print_ticket_tables',
    '0005_add_priority_fields_to_orders',
    '20250728_0130_0016',
    '006_add_rewards_engine',
    '008_pos_analytics',
    '20250725_0454_0005',
    '20250725_2126_0009',
    '20250730_1000',
    '20250731_1000_add_external_pos_webhook_tables',
    '9a7b19d94ae6',
    'add_enhanced_reservation_system',
    'add_manual_review_tables_v2',
    'recipe_performance_indexes',
    'update_inventory_adjustments'
)
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration, no operations needed
    pass


def downgrade():
    # This is a merge migration, no operations needed
    pass