"""Add refund processing tables

Revision ID: add_refund_processing_tables
Revises: add_split_bill_tables
Create Date: 2025-08-04 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_refund_processing_tables'
down_revision = 'add_split_bill_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create refund reason enum
    op.execute("""
        CREATE TYPE refund_reason AS ENUM (
            'order_cancelled', 'order_mistake', 'wrong_items', 'missing_items',
            'food_quality', 'cold_food', 'incorrect_preparation',
            'long_wait', 'poor_service',
            'duplicate_charge', 'overcharge', 'price_dispute',
            'customer_request', 'goodwill', 'test_refund', 'other'
        );
    """)
    
    # Create refund category enum
    op.execute("""
        CREATE TYPE refund_category AS ENUM (
            'order_issue', 'quality_issue', 'service_issue', 
            'payment_issue', 'other'
        );
    """)
    
    # Create refund approval status enum
    op.execute("""
        CREATE TYPE refund_approval_status AS ENUM (
            'pending_approval', 'approved', 'rejected', 'auto_approved'
        );
    """)
    
    # Create refund_policies table
    op.create_table(
        'refund_policies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        
        # Policy settings
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        
        # Automatic approval
        sa.Column('auto_approve_enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_approve_threshold', sa.Numeric(10, 2), nullable=True, server_default='50.00'),
        
        # Time limits
        sa.Column('refund_window_hours', sa.Integer(), nullable=True, server_default='168'),
        
        # Partial refund settings
        sa.Column('allow_partial_refunds', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('min_refund_percentage', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_refund_percentage', sa.Integer(), nullable=True, server_default='100'),
        
        # Requirements
        sa.Column('require_reason', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('require_approval_above', sa.Numeric(10, 2), nullable=True),
        
        # Fee handling
        sa.Column('refund_processing_fee', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('deduct_processing_fee', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processing_fee_amount', sa.Numeric(10, 2), nullable=True, server_default='0'),
        
        # Notifications
        sa.Column('notify_customer', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_manager', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('manager_notification_threshold', sa.Numeric(10, 2), nullable=True, server_default='100.00'),
        
        # Metadata
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id']),
    )
    
    # Create indexes
    op.create_index('idx_refund_policy_restaurant', 'refund_policies', ['restaurant_id', 'is_active'])
    
    # Create refund_requests table
    op.create_table(
        'refund_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_number', sa.String(50), nullable=False),
        
        # Order and payment info
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=False),
        
        # Request details
        sa.Column('requested_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('reason_code', postgresql.ENUM('order_cancelled', 'order_mistake', 'wrong_items', 'missing_items',
                                                 'food_quality', 'cold_food', 'incorrect_preparation',
                                                 'long_wait', 'poor_service',
                                                 'duplicate_charge', 'overcharge', 'price_dispute',
                                                 'customer_request', 'goodwill', 'test_refund', 'other',
                                                 name='refund_reason', create_type=False), nullable=False),
        sa.Column('category', postgresql.ENUM('order_issue', 'quality_issue', 'service_issue', 
                                             'payment_issue', 'other',
                                             name='refund_category', create_type=False), nullable=False),
        sa.Column('reason_details', sa.Text(), nullable=True),
        
        # Customer info
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=False),
        sa.Column('customer_email', sa.String(255), nullable=False),
        sa.Column('customer_phone', sa.String(50), nullable=True),
        
        # Approval workflow
        sa.Column('approval_status', postgresql.ENUM('pending_approval', 'approved', 'rejected', 'auto_approved',
                                                     name='refund_approval_status', create_type=False), 
                 nullable=False, server_default='pending_approval'),
        sa.Column('approved_by', sa.Integer(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        
        # Processing
        sa.Column('refund_id', sa.Integer(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        
        # Items and evidence
        sa.Column('refund_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('evidence_urls', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        
        # Metadata
        sa.Column('priority', sa.String(20), nullable=True, server_default='normal'),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('request_number'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id']),
        sa.ForeignKeyConstraint(['refund_id'], ['refunds.id']),
    )
    
    # Create indexes
    op.create_index('idx_refund_request_number', 'refund_requests', ['request_number'])
    op.create_index('idx_refund_request_status', 'refund_requests', ['approval_status'])
    op.create_index('idx_refund_request_customer', 'refund_requests', ['customer_id'])
    op.create_index('idx_refund_request_order', 'refund_requests', ['order_id'])
    op.create_index('idx_refund_request_category', 'refund_requests', ['category'])
    
    # Create refund_audit_logs table
    op.create_table(
        'refund_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # References
        sa.Column('refund_id', sa.Integer(), nullable=True),
        sa.Column('refund_request_id', sa.Integer(), nullable=True),
        
        # Action details
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column('actor_type', sa.String(20), nullable=True),
        
        # State tracking
        sa.Column('previous_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Additional info
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('audit_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Security
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['refund_id'], ['refunds.id']),
        sa.ForeignKeyConstraint(['refund_request_id'], ['refund_requests.id']),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id']),
    )
    
    # Create indexes
    op.create_index('idx_audit_refund', 'refund_audit_logs', ['refund_id'])
    op.create_index('idx_audit_request', 'refund_audit_logs', ['refund_request_id'])
    op.create_index('idx_audit_action', 'refund_audit_logs', ['action'])
    op.create_index('idx_audit_actor', 'refund_audit_logs', ['actor_id'])
    
    # Add new columns to existing refunds table
    op.add_column('refunds', sa.Column('reason_code', 
                                       postgresql.ENUM('order_cancelled', 'order_mistake', 'wrong_items', 'missing_items',
                                                      'food_quality', 'cold_food', 'incorrect_preparation',
                                                      'long_wait', 'poor_service',
                                                      'duplicate_charge', 'overcharge', 'price_dispute',
                                                      'customer_request', 'goodwill', 'test_refund', 'other',
                                                      name='refund_reason', create_type=False), nullable=True))
    op.add_column('refunds', sa.Column('category', 
                                       postgresql.ENUM('order_issue', 'quality_issue', 'service_issue', 
                                                      'payment_issue', 'other',
                                                      name='refund_category', create_type=False), nullable=True))
    op.add_column('refunds', sa.Column('refund_type', sa.String(20), nullable=True))
    op.add_column('refunds', sa.Column('credit_issued', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('refunds', sa.Column('credit_amount', sa.Numeric(10, 2), nullable=True))
    op.add_column('refunds', sa.Column('original_payment_method', sa.String(50), nullable=True))
    op.add_column('refunds', sa.Column('refund_method', sa.String(50), nullable=True))
    op.add_column('refunds', sa.Column('expected_completion_date', sa.DateTime(), nullable=True))
    op.add_column('refunds', sa.Column('actual_completion_date', sa.DateTime(), nullable=True))
    op.add_column('refunds', sa.Column('notification_sent', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('refunds', sa.Column('notification_sent_at', sa.DateTime(), nullable=True))
    op.add_column('refunds', sa.Column('receipt_url', sa.String(500), nullable=True))
    op.add_column('refunds', sa.Column('batch_id', sa.String(50), nullable=True))
    op.add_column('refunds', sa.Column('is_disputed', sa.Boolean(), nullable=True, server_default='false'))
    op.add_column('refunds', sa.Column('dispute_notes', sa.Text(), nullable=True))
    
    # Add triggers for updated_at
    for table in ['refund_policies', 'refund_requests', 'refund_audit_logs']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # Insert a default refund policy for demo
    op.execute("""
        INSERT INTO refund_policies (restaurant_id, name, description, is_default, auto_approve_enabled, auto_approve_threshold)
        VALUES (
            1, 
            'Default Refund Policy', 
            'Standard refund policy with 7-day window and auto-approval for amounts under $50',
            true,
            true,
            50.00
        )
        ON CONFLICT DO NOTHING;
    """)


def downgrade():
    # Drop triggers
    for table in ['refund_policies', 'refund_requests', 'refund_audit_logs']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    # Drop new columns from refunds table
    op.drop_column('refunds', 'dispute_notes')
    op.drop_column('refunds', 'is_disputed')
    op.drop_column('refunds', 'batch_id')
    op.drop_column('refunds', 'receipt_url')
    op.drop_column('refunds', 'notification_sent_at')
    op.drop_column('refunds', 'notification_sent')
    op.drop_column('refunds', 'actual_completion_date')
    op.drop_column('refunds', 'expected_completion_date')
    op.drop_column('refunds', 'refund_method')
    op.drop_column('refunds', 'original_payment_method')
    op.drop_column('refunds', 'credit_amount')
    op.drop_column('refunds', 'credit_issued')
    op.drop_column('refunds', 'refund_type')
    op.drop_column('refunds', 'category')
    op.drop_column('refunds', 'reason_code')
    
    # Drop tables
    op.drop_table('refund_audit_logs')
    op.drop_table('refund_requests')
    op.drop_table('refund_policies')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS refund_approval_status;")
    op.execute("DROP TYPE IF EXISTS refund_category;")
    op.execute("DROP TYPE IF EXISTS refund_reason;")