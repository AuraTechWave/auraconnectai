"""Add manual review tables for inventory error handling

Revision ID: add_manual_review_tables
Revises: 
Create Date: 2025-08-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_manual_review_tables'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types with IF NOT EXISTS check
    connection = op.get_bind()
    
    # Check if reviewreason type exists
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'reviewreason'"
    ))
    if not result.fetchone():
        op.execute("CREATE TYPE reviewreason AS ENUM ('missing_recipe', 'insufficient_stock', 'inventory_not_found', 'recipe_circular_dependency', 'sync_conflict', 'concurrent_modification', 'other')")
    
    # Create manual review status type with different name to avoid conflict
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'manualreviewstatus'"
    ))
    if not result.fetchone():
        op.execute("CREATE TYPE manualreviewstatus AS ENUM ('pending', 'in_review', 'resolved', 'escalated', 'cancelled')")
    
    # Create manual_review_queue table
    op.create_table(
        'manual_review_queue',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('reason', postgresql.ENUM('missing_recipe', 'insufficient_stock', 'inventory_not_found', 
                                           'recipe_circular_dependency', 'sync_conflict', 'concurrent_modification', 
                                           'other', name='reviewreason'), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'in_review', 'resolved', 'escalated', 'cancelled', 
                                           name='manualreviewstatus'), nullable=False),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('assigned_to', sa.Integer(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('review_notes', sa.Text(), nullable=True),
        sa.Column('resolution_action', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('escalated', sa.Boolean(), nullable=False),
        sa.Column('escalation_reason', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_manual_review_queue_order_id'), 'manual_review_queue', ['order_id'], unique=False)
    op.create_index('ix_manual_review_queue_status_priority', 'manual_review_queue', ['status', 'priority'], unique=False)
    
    # Create inventory_adjustment_attempts table
    op.create_table(
        'inventory_adjustment_attempts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('error_type', sa.String(100), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=False),
        sa.Column('error_details', sa.JSON(), nullable=True),
        sa.Column('attempted_deductions', sa.JSON(), nullable=True),
        sa.Column('menu_items_affected', sa.JSON(), nullable=True),
        sa.Column('attempted_at', sa.DateTime(), nullable=False),
        sa.Column('attempted_by', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['attempted_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_inventory_adjustment_attempts_order_id'), 'inventory_adjustment_attempts', ['order_id'], unique=False)
    
    # Add columns to orders table for manual review tracking
    # Add requires_manual_review with server default of false
    op.add_column('orders', sa.Column(
        'requires_manual_review', 
        sa.Boolean(), 
        nullable=False,
        server_default=sa.false()
    ))
    
    # Add review_reason as nullable
    op.add_column('orders', sa.Column('review_reason', sa.String(50), nullable=True))


def downgrade():
    # Drop columns from orders table
    op.drop_column('orders', 'review_reason')
    op.drop_column('orders', 'requires_manual_review')
    
    # Drop tables
    op.drop_index(op.f('ix_inventory_adjustment_attempts_order_id'), table_name='inventory_adjustment_attempts')
    op.drop_table('inventory_adjustment_attempts')
    
    op.drop_index('ix_manual_review_queue_status_priority', table_name='manual_review_queue')
    op.drop_index(op.f('ix_manual_review_queue_order_id'), table_name='manual_review_queue')
    op.drop_table('manual_review_queue')
    
    # Drop enum types
    op.execute('DROP TYPE IF EXISTS manualreviewstatus')
    op.execute('DROP TYPE IF EXISTS reviewreason')