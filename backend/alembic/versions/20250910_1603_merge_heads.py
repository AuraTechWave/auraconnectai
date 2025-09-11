# Auto-generated merge migration
# Created by create_merge_heads.py

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250910_1603_merge_heads'
down_revision = ('0017', 'pos_migration_001', 'create_materialized_views_2025_01_21', 'add_pricing_rules_tables', '20250727_2200_0015', 'enhance_shift_swap_workflow', 'add_audit_logs_table', '20250727_1600_0012', 'add_health_monitoring_tables', '20250804_2100', 'add_order_splitting', '0013_add_password_security', 'recipe_performance_indexes', 'update_inventory_adjustments', 'create_core_models_20250111', '20250822_add_email_notification_system', 'fix_customer_lifetime_value', 'add_manual_review_tables', 'add_enhanced_reservation_system')
branch_labels = None
depends_on = None


def upgrade():
    # This is a merge migration; no schema changes.
    pass


def downgrade():
    # This is a merge migration; no schema changes.
    pass
