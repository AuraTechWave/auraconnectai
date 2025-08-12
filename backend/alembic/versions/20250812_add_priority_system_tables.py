"""Add priority system tables

Revision ID: add_priority_system
Revises: add_order_splitting_tables
Create Date: 2025-08-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_priority_system'
down_revision = 'add_order_splitting_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types
    op.execute("CREATE TYPE priorityalgorithmtype AS ENUM ('preparation_time', 'delivery_window', 'vip_status', 'order_value', 'wait_time', 'item_complexity', 'composite', 'custom')")
    op.execute("CREATE TYPE priorityscoretype AS ENUM ('linear', 'exponential', 'logarithmic', 'step', 'custom')")
    
    # Create priority_rules table
    op.create_table('priority_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('algorithm_type', postgresql.ENUM('preparation_time', 'delivery_window', 'vip_status', 'order_value', 'wait_time', 'item_complexity', 'composite', 'custom', name='priorityalgorithmtype', create_type=False), nullable=False),
        sa.Column('score_type', postgresql.ENUM('linear', 'exponential', 'logarithmic', 'step', 'custom', name='priorityscoretype', create_type=False), nullable=False),
        sa.Column('base_score', sa.Float(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False),
        sa.Column('parameters', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('conditions', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_priority_rules_algorithm_type'), 'priority_rules', ['algorithm_type'], unique=False)
    op.create_index(op.f('ix_priority_rules_id'), 'priority_rules', ['id'], unique=False)
    op.create_index(op.f('ix_priority_rules_restaurant_id'), 'priority_rules', ['restaurant_id'], unique=False)
    
    # Create priority_profiles table
    op.create_table('priority_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_priority_profiles_id'), 'priority_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_priority_profiles_restaurant_id'), 'priority_profiles', ['restaurant_id'], unique=False)
    
    # Create priority_profile_rules table
    op.create_table('priority_profile_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('custom_weight', sa.Float(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['priority_profiles.id'], ),
        sa.ForeignKeyConstraint(['rule_id'], ['priority_rules.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id', 'rule_id')
    )
    op.create_index(op.f('ix_priority_profile_rules_id'), 'priority_profile_rules', ['id'], unique=False)
    
    # Create queue_priority_configs table
    op.create_table('queue_priority_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('min_score_threshold', sa.Float(), nullable=True),
        sa.Column('max_score_threshold', sa.Float(), nullable=True),
        sa.Column('auto_rebalance', sa.Boolean(), nullable=False),
        sa.Column('rebalance_interval_minutes', sa.Integer(), nullable=True),
        sa.Column('last_rebalance_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['priority_profiles.id'], ),
        sa.ForeignKeyConstraint(['queue_id'], ['order_queues.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_id')
    )
    op.create_index(op.f('ix_queue_priority_configs_id'), 'queue_priority_configs', ['id'], unique=False)
    
    # Create order_priority_scores table
    op.create_table('order_priority_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('score_components', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['profile_id'], ['priority_profiles.id'], ),
        sa.ForeignKeyConstraint(['queue_id'], ['order_queues.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_order_priority_order_queue', 'order_priority_scores', ['order_id', 'queue_id'], unique=False)
    op.create_index('idx_score_components_gin', 'order_priority_scores', ['score_components'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_order_priority_scores_calculated_at'), 'order_priority_scores', ['calculated_at'], unique=False)
    op.create_index(op.f('ix_order_priority_scores_id'), 'order_priority_scores', ['id'], unique=False)
    op.create_index(op.f('ix_order_priority_scores_order_id'), 'order_priority_scores', ['order_id'], unique=False)
    
    # Create priority_adjustment_logs table
    op.create_table('priority_adjustment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('old_score', sa.Float(), nullable=True),
        sa.Column('new_score', sa.Float(), nullable=False),
        sa.Column('old_position', sa.Integer(), nullable=True),
        sa.Column('new_position', sa.Integer(), nullable=True),
        sa.Column('adjustment_reason', sa.String(length=100), nullable=False),
        sa.Column('adjustment_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('adjusted_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['adjusted_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['queue_id'], ['order_queues.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_priority_adjustment_logs_created_at'), 'priority_adjustment_logs', ['created_at'], unique=False)
    op.create_index(op.f('ix_priority_adjustment_logs_id'), 'priority_adjustment_logs', ['id'], unique=False)
    op.create_index(op.f('ix_priority_adjustment_logs_order_id'), 'priority_adjustment_logs', ['order_id'], unique=False)
    
    # Create priority_metrics table
    op.create_table('priority_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('metric_date', sa.Date(), nullable=False),
        sa.Column('avg_priority_score', sa.Float(), nullable=True),
        sa.Column('std_dev_priority_score', sa.Float(), nullable=True),
        sa.Column('total_adjustments', sa.Integer(), nullable=True),
        sa.Column('manual_adjustments', sa.Integer(), nullable=True),
        sa.Column('auto_adjustments', sa.Integer(), nullable=True),
        sa.Column('fairness_index', sa.Float(), nullable=True),
        sa.Column('metrics_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['queue_id'], ['order_queues.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_id', 'metric_date')
    )
    op.create_index('idx_metrics_data_gin', 'priority_metrics', ['metrics_data'], unique=False, postgresql_using='gin')
    op.create_index(op.f('ix_priority_metrics_id'), 'priority_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_priority_metrics_metric_date'), 'priority_metrics', ['metric_date'], unique=False)


def downgrade():
    # Drop tables in reverse order
    op.drop_index(op.f('ix_priority_metrics_metric_date'), table_name='priority_metrics')
    op.drop_index(op.f('ix_priority_metrics_id'), table_name='priority_metrics')
    op.drop_index('idx_metrics_data_gin', table_name='priority_metrics')
    op.drop_table('priority_metrics')
    
    op.drop_index(op.f('ix_priority_adjustment_logs_order_id'), table_name='priority_adjustment_logs')
    op.drop_index(op.f('ix_priority_adjustment_logs_id'), table_name='priority_adjustment_logs')
    op.drop_index(op.f('ix_priority_adjustment_logs_created_at'), table_name='priority_adjustment_logs')
    op.drop_table('priority_adjustment_logs')
    
    op.drop_index(op.f('ix_order_priority_scores_order_id'), table_name='order_priority_scores')
    op.drop_index(op.f('ix_order_priority_scores_id'), table_name='order_priority_scores')
    op.drop_index(op.f('ix_order_priority_scores_calculated_at'), table_name='order_priority_scores')
    op.drop_index('idx_score_components_gin', table_name='order_priority_scores')
    op.drop_index('idx_order_priority_order_queue', table_name='order_priority_scores')
    op.drop_table('order_priority_scores')
    
    op.drop_index(op.f('ix_queue_priority_configs_id'), table_name='queue_priority_configs')
    op.drop_table('queue_priority_configs')
    
    op.drop_index(op.f('ix_priority_profile_rules_id'), table_name='priority_profile_rules')
    op.drop_table('priority_profile_rules')
    
    op.drop_index(op.f('ix_priority_profiles_restaurant_id'), table_name='priority_profiles')
    op.drop_index(op.f('ix_priority_profiles_id'), table_name='priority_profiles')
    op.drop_table('priority_profiles')
    
    op.drop_index(op.f('ix_priority_rules_restaurant_id'), table_name='priority_rules')
    op.drop_index(op.f('ix_priority_rules_id'), table_name='priority_rules')
    op.drop_index(op.f('ix_priority_rules_algorithm_type'), table_name='priority_rules')
    op.drop_table('priority_rules')
    
    # Drop enum types
    op.execute("DROP TYPE priorityscoretype")
    op.execute("DROP TYPE priorityalgorithmtype")