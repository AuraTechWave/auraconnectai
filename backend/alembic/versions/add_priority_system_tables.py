"""Add priority system tables

Revision ID: add_priority_system
Revises: add_order_splitting_tables
Create Date: 2025-08-12 10:00:00.000000

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
    op.execute("CREATE TYPE priorityalgorithm AS ENUM ('fifo', 'weighted', 'dynamic', 'custom', 'fair_share', 'revenue_optimized')")
    op.execute("CREATE TYPE priorityscoretype AS ENUM ('wait_time', 'order_value', 'vip_status', 'delivery_time', 'prep_complexity', 'customer_loyalty', 'peak_hours', 'group_size', 'special_needs', 'custom')")
    
    # Create priority_rules table
    op.create_table('priority_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('score_type', postgresql.ENUM('wait_time', 'order_value', 'vip_status', 'delivery_time', 'prep_complexity', 'customer_loyalty', 'peak_hours', 'group_size', 'special_needs', 'custom', name='priorityscoretype', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('score_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('min_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('max_score', sa.Float(), nullable=True, server_default='100.0'),
        sa.Column('default_weight', sa.Float(), nullable=True, server_default='1.0'),
        sa.Column('normalize_output', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('normalization_method', sa.String(length=50), nullable=True, server_default='min_max'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sa.CheckConstraint('min_score <= max_score', name='check_score_range'),
        sa.CheckConstraint('default_weight >= 0', name='check_positive_weight')
    )
    op.create_index(op.f('ix_priority_rules_score_type'), 'priority_rules', ['score_type'], unique=False)
    
    # Create priority_profiles table
    op.create_table('priority_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('algorithm_type', postgresql.ENUM('fifo', 'weighted', 'dynamic', 'custom', 'fair_share', 'revenue_optimized', name='priorityalgorithm', create_type=False), nullable=False, server_default='weighted'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('aggregation_method', sa.String(length=50), nullable=True, server_default='weighted_sum'),
        sa.Column('total_weight_normalization', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('min_total_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('max_total_score', sa.Float(), nullable=True, server_default='100.0'),
        sa.Column('cache_duration_seconds', sa.Integer(), nullable=True, server_default='60'),
        sa.Column('recalculation_threshold', sa.Float(), nullable=True, server_default='0.1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_profile_active_default', 'priority_profiles', ['is_active', 'is_default'], unique=False)
    
    # Create priority_profile_rules table
    op.create_table('priority_profile_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('override_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('boost_conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['priority_profiles.id'], ),
        sa.ForeignKeyConstraint(['rule_id'], ['priority_rules.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('profile_id', 'rule_id', name='uq_profile_rule'),
        sa.CheckConstraint('weight >= 0', name='check_positive_rule_weight')
    )
    
    # Create queue_priority_configs table
    op.create_table('queue_priority_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('priority_enabled', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('auto_rebalance', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('rebalance_interval_minutes', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('rebalance_threshold', sa.Float(), nullable=True, server_default='0.2'),
        sa.Column('last_rebalance_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('max_position_change', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('boost_new_items', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('boost_duration_seconds', sa.Integer(), nullable=True, server_default='30'),
        sa.Column('queue_overrides', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('peak_hours_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['profile_id'], ['priority_profiles.id'], ),
        sa.ForeignKeyConstraint(['queue_id'], ['order_queues.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_id')
    )
    op.create_index('idx_queue_priority_active', 'queue_priority_configs', ['queue_id', 'is_active'], unique=False)
    
    # Create order_priority_scores table
    op.create_table('order_priority_scores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_item_id', sa.Integer(), nullable=False),
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('total_score', sa.Float(), nullable=False),
        sa.Column('base_score', sa.Float(), nullable=False),
        sa.Column('boost_score', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('score_components', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('calculated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('algorithm_version', sa.String(length=20), nullable=True),
        sa.Column('calculation_time_ms', sa.Integer(), nullable=True),
        sa.Column('is_boosted', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('boost_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('boost_reason', sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(['config_id'], ['queue_priority_configs.id'], ),
        sa.ForeignKeyConstraint(['queue_item_id'], ['queue_items.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_item_id')
    )
    op.create_index(op.f('ix_order_priority_scores_total_score'), 'order_priority_scores', ['total_score'], unique=False)
    op.create_index('idx_priority_score_queue', 'order_priority_scores', ['config_id', 'total_score'], unique=False)
    op.create_index('idx_priority_score_boost', 'order_priority_scores', ['is_boosted', 'boost_expires_at'], unique=False)
    
    # Create JSONB index for score_components
    op.execute("CREATE INDEX idx_score_components_gin ON order_priority_scores USING gin (score_components)")
    
    # Create priority_adjustment_logs table
    op.create_table('priority_adjustment_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_item_id', sa.Integer(), nullable=False),
        sa.Column('old_score', sa.Float(), nullable=False),
        sa.Column('new_score', sa.Float(), nullable=False),
        sa.Column('adjustment_type', sa.String(length=50), nullable=False),
        sa.Column('adjustment_reason', sa.String(length=200), nullable=True),
        sa.Column('old_position', sa.Integer(), nullable=True),
        sa.Column('new_position', sa.Integer(), nullable=True),
        sa.Column('adjusted_by_id', sa.Integer(), nullable=True),
        sa.Column('adjusted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['adjusted_by_id'], ['staff_members.id'], ),
        sa.ForeignKeyConstraint(['queue_item_id'], ['queue_items.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_priority_adjustment_logs_queue_item_id'), 'priority_adjustment_logs', ['queue_item_id'], unique=False)
    
    # Create priority_metrics table
    op.create_table('priority_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('queue_id', sa.Integer(), nullable=False),
        sa.Column('metric_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('hour_of_day', sa.Integer(), nullable=True),
        sa.Column('gini_coefficient', sa.Float(), nullable=True),
        sa.Column('max_wait_variance', sa.Float(), nullable=True),
        sa.Column('position_change_avg', sa.Float(), nullable=True),
        sa.Column('avg_calculation_time_ms', sa.Float(), nullable=True),
        sa.Column('total_calculations', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cache_hit_rate', sa.Float(), nullable=True),
        sa.Column('rebalance_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('avg_rebalance_impact', sa.Float(), nullable=True),
        sa.Column('manual_adjustments', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('revenue_impact', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('customer_satisfaction_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['queue_id'], ['order_queues.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('queue_id', 'metric_date', 'hour_of_day', name='uq_priority_metrics_period')
    )
    op.create_index(op.f('ix_priority_metrics_queue_id'), 'priority_metrics', ['queue_id'], unique=False)
    op.create_index('idx_priority_metrics_date', 'priority_metrics', ['queue_id', 'metric_date'], unique=False)


def downgrade():
    # Drop tables in reverse order of creation
    op.drop_index('idx_priority_metrics_date', table_name='priority_metrics')
    op.drop_index(op.f('ix_priority_metrics_queue_id'), table_name='priority_metrics')
    op.drop_table('priority_metrics')
    
    op.drop_index(op.f('ix_priority_adjustment_logs_queue_item_id'), table_name='priority_adjustment_logs')
    op.drop_table('priority_adjustment_logs')
    
    op.execute("DROP INDEX idx_score_components_gin")
    op.drop_index('idx_priority_score_boost', table_name='order_priority_scores')
    op.drop_index('idx_priority_score_queue', table_name='order_priority_scores')
    op.drop_index(op.f('ix_order_priority_scores_total_score'), table_name='order_priority_scores')
    op.drop_table('order_priority_scores')
    
    op.drop_index('idx_queue_priority_active', table_name='queue_priority_configs')
    op.drop_table('queue_priority_configs')
    
    op.drop_table('priority_profile_rules')
    
    op.drop_index('idx_profile_active_default', table_name='priority_profiles')
    op.drop_table('priority_profiles')
    
    op.drop_index(op.f('ix_priority_rules_score_type'), table_name='priority_rules')
    op.drop_table('priority_rules')
    
    # Drop enum types
    op.execute("DROP TYPE priorityscoretype")
    op.execute("DROP TYPE priorityalgorithm")