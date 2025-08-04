"""Add split bill and tip management tables

Revision ID: add_split_bill_tables
Revises: add_payment_gateway_tables
Create Date: 2025-08-04 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_split_bill_tables'
down_revision = 'add_payment_gateway_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create split method enum
    op.execute("""
        CREATE TYPE split_method AS ENUM (
            'equal', 'percentage', 'amount', 'item', 'custom'
        );
    """)
    
    # Create split status enum
    op.execute("""
        CREATE TYPE split_status AS ENUM (
            'pending', 'active', 'partially_paid', 'completed', 'cancelled'
        );
    """)
    
    # Create participant status enum
    op.execute("""
        CREATE TYPE participant_status AS ENUM (
            'pending', 'accepted', 'declined', 'paid', 'refunded'
        );
    """)
    
    # Create tip method enum
    op.execute("""
        CREATE TYPE tip_method AS ENUM (
            'percentage', 'amount', 'round_up'
        );
    """)
    
    # Create bill_splits table
    op.create_table(
        'bill_splits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('split_id', sa.String(100), nullable=False),
        
        # Order relationship
        sa.Column('order_id', sa.Integer(), nullable=False),
        
        # Split configuration
        sa.Column('split_method', postgresql.ENUM('equal', 'percentage', 'amount', 'item', 'custom',
                                                  name='split_method', create_type=False), 
                 nullable=False, server_default='equal'),
        sa.Column('status', postgresql.ENUM('pending', 'active', 'partially_paid', 'completed', 'cancelled',
                                           name='split_status', create_type=False), 
                 nullable=False, server_default='pending'),
        
        # Amounts
        sa.Column('subtotal', sa.Numeric(10, 2), nullable=False),
        sa.Column('tax_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('service_charge', sa.Numeric(10, 2), nullable=False, server_default='0'),
        
        # Tip configuration
        sa.Column('tip_method', postgresql.ENUM('percentage', 'amount', 'round_up',
                                               name='tip_method', create_type=False), nullable=True),
        sa.Column('tip_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('tip_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
        
        # Split configuration details
        sa.Column('split_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Organizer info
        sa.Column('organizer_id', sa.Integer(), nullable=True),
        sa.Column('organizer_name', sa.String(255), nullable=True),
        sa.Column('organizer_email', sa.String(255), nullable=True),
        sa.Column('organizer_phone', sa.String(50), nullable=True),
        
        # Settings
        sa.Column('allow_partial_payments', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('require_all_acceptance', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('auto_close_on_completion', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        
        # Notification settings
        sa.Column('send_reminders', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('reminder_sent_at', sa.DateTime(), nullable=True),
        
        # Metadata
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('split_id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['organizer_id'], ['customers.id']),
    )
    
    # Create indexes for bill_splits
    op.create_index('idx_bill_split_order_status', 'bill_splits', ['order_id', 'status'])
    op.create_index('idx_bill_split_organizer', 'bill_splits', ['organizer_id'])
    op.create_index('idx_bill_split_status', 'bill_splits', ['status'])
    
    # Create split_participants table
    op.create_table(
        'split_participants',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Split relationship
        sa.Column('split_id', sa.Integer(), nullable=False),
        
        # Participant info
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),
        
        # Share details
        sa.Column('share_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('tip_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(10, 2), nullable=False),
        
        # Custom tip override
        sa.Column('custom_tip_amount', sa.Numeric(10, 2), nullable=True),
        
        # Payment status
        sa.Column('status', postgresql.ENUM('pending', 'accepted', 'declined', 'paid', 'refunded',
                                           name='participant_status', create_type=False), 
                 nullable=False, server_default='pending'),
        sa.Column('paid_amount', sa.Numeric(10, 2), nullable=False, server_default='0'),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        
        # Acceptance tracking
        sa.Column('invite_sent_at', sa.DateTime(), nullable=True),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('declined_at', sa.DateTime(), nullable=True),
        sa.Column('decline_reason', sa.Text(), nullable=True),
        
        # Access token for guest participants
        sa.Column('access_token', sa.String(255), nullable=True),
        
        # Notification preferences
        sa.Column('notify_via_email', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('notify_via_sms', sa.Boolean(), nullable=False, server_default='false'),
        
        # Metadata
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('split_id', 'email', name='uq_split_participant_email'),
        sa.UniqueConstraint('access_token'),
        sa.ForeignKeyConstraint(['split_id'], ['bill_splits.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
    )
    
    # Create indexes for split_participants
    op.create_index('idx_participant_split_status', 'split_participants', ['split_id', 'status'])
    op.create_index('idx_participant_customer', 'split_participants', ['customer_id'])
    op.create_index('idx_participant_access_token', 'split_participants', ['access_token'])
    
    # Create payment_allocations table
    op.create_table(
        'payment_allocations',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Payment and split references
        sa.Column('payment_id', sa.Integer(), nullable=False),
        sa.Column('split_id', sa.Integer(), nullable=False),
        sa.Column('participant_id', sa.Integer(), nullable=False),
        
        # Allocation details
        sa.Column('allocated_amount', sa.Numeric(10, 2), nullable=False),
        
        # What this allocation covers
        sa.Column('covers_share', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('covers_tip', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('covers_fees', sa.Boolean(), nullable=False, server_default='false'),
        
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        
        # Metadata
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id', 'split_id', 'participant_id', name='uq_payment_split_participant'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['split_id'], ['bill_splits.id']),
        sa.ForeignKeyConstraint(['participant_id'], ['split_participants.id']),
    )
    
    # Create indexes for payment_allocations
    op.create_index('idx_allocation_payment', 'payment_allocations', ['payment_id'])
    op.create_index('idx_allocation_split', 'payment_allocations', ['split_id'])
    op.create_index('idx_allocation_participant', 'payment_allocations', ['participant_id'])
    
    # Create tip_distributions table
    op.create_table(
        'tip_distributions',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Source of tip
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('split_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        
        # Tip details
        sa.Column('tip_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('distribution_method', sa.String(50), nullable=False, server_default='pool'),
        
        # Distribution configuration
        sa.Column('distribution_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Status
        sa.Column('is_distributed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('distributed_at', sa.DateTime(), nullable=True),
        sa.Column('distributed_by', sa.Integer(), nullable=True),
        
        # Actual distributions
        sa.Column('distributions', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        
        # Metadata
        sa.Column('notes', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['split_id'], ['bill_splits.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['distributed_by'], ['users.id']),
    )
    
    # Create indexes for tip_distributions
    op.create_index('idx_tip_dist_order', 'tip_distributions', ['order_id'])
    op.create_index('idx_tip_dist_split', 'tip_distributions', ['split_id'])
    op.create_index('idx_tip_dist_status', 'tip_distributions', ['is_distributed'])
    
    # Add triggers for updated_at
    for table in ['bill_splits', 'split_participants', 'payment_allocations', 'tip_distributions']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # Add split_id column to payments table for tracking split payments
    op.add_column('payments', sa.Column('split_id', sa.Integer(), nullable=True))
    op.add_column('payments', sa.Column('participant_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_payment_split', 'payments', 'bill_splits', ['split_id'], ['id'])
    op.create_foreign_key('fk_payment_participant', 'payments', 'split_participants', ['participant_id'], ['id'])
    op.create_index('idx_payment_split', 'payments', ['split_id'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_payment_split', 'payments')
    
    # Drop foreign keys and columns from payments
    op.drop_constraint('fk_payment_participant', 'payments', type_='foreignkey')
    op.drop_constraint('fk_payment_split', 'payments', type_='foreignkey')
    op.drop_column('payments', 'participant_id')
    op.drop_column('payments', 'split_id')
    
    # Drop triggers
    for table in ['bill_splits', 'split_participants', 'payment_allocations', 'tip_distributions']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    # Drop tables in reverse order
    op.drop_table('tip_distributions')
    op.drop_table('payment_allocations')
    op.drop_table('split_participants')
    op.drop_table('bill_splits')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS tip_method;")
    op.execute("DROP TYPE IF EXISTS participant_status;")
    op.execute("DROP TYPE IF EXISTS split_status;")
    op.execute("DROP TYPE IF EXISTS split_method;")