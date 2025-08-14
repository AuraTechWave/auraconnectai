"""Enhance shift swap workflow

Revision ID: enhance_shift_swap_workflow
Revises: add_priority_system
Create Date: 2025-08-12

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'enhance_shift_swap_workflow'
down_revision = 'add_priority_system'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to shift_swaps table
    op.add_column('shift_swaps', sa.Column('approval_level', sa.String(length=50), nullable=True))
    op.add_column('shift_swaps', sa.Column('requires_secondary_approval', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('shift_swaps', sa.Column('secondary_approver_id', sa.Integer(), nullable=True))
    op.add_column('shift_swaps', sa.Column('secondary_approved_at', sa.DateTime(), nullable=True))
    op.add_column('shift_swaps', sa.Column('rejection_reason', sa.Text(), nullable=True))
    op.add_column('shift_swaps', sa.Column('requester_notified', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('shift_swaps', sa.Column('to_staff_notified', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('shift_swaps', sa.Column('manager_notified', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('shift_swaps', sa.Column('notification_sent_at', sa.DateTime(), nullable=True))
    op.add_column('shift_swaps', sa.Column('auto_approval_eligible', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('shift_swaps', sa.Column('auto_approval_reason', sa.String(length=200), nullable=True))
    op.add_column('shift_swaps', sa.Column('response_deadline', sa.DateTime(), nullable=True))
    
    # Add foreign key for secondary approver
    op.create_foreign_key(
        'fk_shift_swaps_secondary_approver',
        'shift_swaps', 'staff_members',
        ['secondary_approver_id'], ['id']
    )
    
    # Create swap_approval_rules table
    op.create_table('swap_approval_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        sa.Column('rule_name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_hours_difference', sa.Float(), nullable=True),
        sa.Column('same_role_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('same_location_required', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('min_advance_notice_hours', sa.Integer(), nullable=False, server_default='24'),
        sa.Column('max_advance_notice_hours', sa.Integer(), nullable=True),
        sa.Column('min_tenure_days', sa.Integer(), nullable=False, server_default='90'),
        sa.Column('max_swaps_per_month', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('no_recent_violations', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('performance_rating_min', sa.Float(), nullable=True),
        sa.Column('blackout_dates', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('restricted_shifts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('peak_hours_restricted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('requires_manager_approval', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('requires_both_staff_consent', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('approval_timeout_hours', sa.Integer(), nullable=False, server_default='48'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_swap_approval_rules_id'), 'swap_approval_rules', ['id'], unique=False)
    op.create_index(op.f('ix_swap_approval_rules_restaurant_id'), 'swap_approval_rules', ['restaurant_id'], unique=False)
    op.create_index('idx_swap_approval_rules_active', 'swap_approval_rules', ['restaurant_id', 'is_active'], unique=False)
    op.create_index('idx_swap_approval_rules_priority', 'swap_approval_rules', ['restaurant_id', 'priority'], unique=False)
    
    # Create indexes for shift_swaps
    op.create_index('idx_shift_swaps_pending', 'shift_swaps', ['status'], unique=False, 
                    postgresql_where="status = 'pending'")
    op.create_index('idx_shift_swaps_auto_approval', 'shift_swaps', ['auto_approval_eligible'], unique=False)
    op.create_index('idx_shift_swaps_deadline', 'shift_swaps', ['response_deadline'], unique=False)
    # Add composite index for monthly swap limit queries
    op.create_index('idx_shift_swaps_requester_created', 'shift_swaps', ['requester_id', 'created_at'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('idx_shift_swaps_requester_created', table_name='shift_swaps')
    op.drop_index('idx_shift_swaps_deadline', table_name='shift_swaps')
    op.drop_index('idx_shift_swaps_auto_approval', table_name='shift_swaps')
    op.drop_index('idx_shift_swaps_pending', table_name='shift_swaps')
    op.drop_index('idx_swap_approval_rules_priority', table_name='swap_approval_rules')
    op.drop_index('idx_swap_approval_rules_active', table_name='swap_approval_rules')
    op.drop_index(op.f('ix_swap_approval_rules_restaurant_id'), table_name='swap_approval_rules')
    op.drop_index(op.f('ix_swap_approval_rules_id'), table_name='swap_approval_rules')
    
    # Drop table
    op.drop_table('swap_approval_rules')
    
    # Drop foreign key
    op.drop_constraint('fk_shift_swaps_secondary_approver', 'shift_swaps', type_='foreignkey')
    
    # Drop columns from shift_swaps
    op.drop_column('shift_swaps', 'response_deadline')
    op.drop_column('shift_swaps', 'auto_approval_reason')
    op.drop_column('shift_swaps', 'auto_approval_eligible')
    op.drop_column('shift_swaps', 'notification_sent_at')
    op.drop_column('shift_swaps', 'manager_notified')
    op.drop_column('shift_swaps', 'to_staff_notified')
    op.drop_column('shift_swaps', 'requester_notified')
    op.drop_column('shift_swaps', 'rejection_reason')
    op.drop_column('shift_swaps', 'secondary_approved_at')
    op.drop_column('shift_swaps', 'secondary_approver_id')
    op.drop_column('shift_swaps', 'requires_secondary_approval')
    op.drop_column('shift_swaps', 'approval_level')