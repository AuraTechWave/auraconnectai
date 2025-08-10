"""Add manual review tables for inventory error handling v2

Revision ID: add_manual_review_tables_v2
Revises: merge_all_heads
Create Date: 2025-08-09

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_manual_review_tables_v2'
down_revision = 'merge_all_heads'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types with proper error handling
    connection = op.get_bind()
    
    # Check and create reviewreason enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'reviewreason'"
    ))
    if not result.fetchone():
        op.execute("CREATE TYPE reviewreason AS ENUM ('missing_recipe', 'insufficient_stock', 'inventory_not_found', 'recipe_circular_dependency', 'sync_conflict', 'concurrent_modification', 'other')")
    
    # Check and create manualreviewstatus enum
    result = connection.execute(sa.text(
        "SELECT 1 FROM pg_type WHERE typname = 'manualreviewstatus'"
    ))
    if not result.fetchone():
        op.execute("CREATE TYPE manualreviewstatus AS ENUM ('pending', 'in_review', 'resolved', 'escalated', 'cancelled')")
    
    # Check if manual_review_queue table already exists
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'manual_review_queue'"
    ))
    if not result.fetchone():
        # Create manual_review_queue table
        op.create_table(
            'manual_review_queue',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('order_id', sa.Integer(), nullable=False),
            sa.Column('reason', postgresql.ENUM('missing_recipe', 'insufficient_stock', 'inventory_not_found', 
                                               'recipe_circular_dependency', 'sync_conflict', 'concurrent_modification', 
                                               'other', name='reviewreason', create_type=False), nullable=False),
            sa.Column('status', postgresql.ENUM('pending', 'in_review', 'resolved', 'escalated', 'cancelled', 
                                               name='manualreviewstatus', create_type=False), nullable=False),
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
    
    # Check if inventory_adjustment_attempts table already exists
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'inventory_adjustment_attempts'"
    ))
    if not result.fetchone():
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
    
    # Check if columns exist before adding them to orders table
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'orders' AND column_name = 'requires_manual_review'"
    ))
    if not result.fetchone():
        op.add_column('orders', sa.Column(
            'requires_manual_review', 
            sa.Boolean(), 
            nullable=False,
            server_default=sa.false()
        ))
    
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'orders' AND column_name = 'review_reason'"
    ))
    if not result.fetchone():
        op.add_column('orders', sa.Column('review_reason', sa.String(50), nullable=True))


def downgrade():
    # Drop columns from orders table if they exist
    connection = op.get_bind()
    
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'orders' AND column_name = 'review_reason'"
    ))
    if result.fetchone():
        op.drop_column('orders', 'review_reason')
    
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'orders' AND column_name = 'requires_manual_review'"
    ))
    if result.fetchone():
        op.drop_column('orders', 'requires_manual_review')
    
    # Drop tables if they exist
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'inventory_adjustment_attempts'"
    ))
    if result.fetchone():
        op.drop_index(op.f('ix_inventory_adjustment_attempts_order_id'), table_name='inventory_adjustment_attempts')
        op.drop_table('inventory_adjustment_attempts')
    
    result = connection.execute(sa.text(
        "SELECT 1 FROM information_schema.tables WHERE table_name = 'manual_review_queue'"
    ))
    if result.fetchone():
        op.drop_index('ix_manual_review_queue_status_priority', table_name='manual_review_queue')
        op.drop_index(op.f('ix_manual_review_queue_order_id'), table_name='manual_review_queue')
        op.drop_table('manual_review_queue')
    
    # Drop enum types if they exist
    op.execute('DROP TYPE IF EXISTS manualreviewstatus')
    op.execute('DROP TYPE IF EXISTS reviewreason')