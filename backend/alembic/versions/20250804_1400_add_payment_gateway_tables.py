"""Add payment gateway integration tables

Revision ID: add_payment_gateway_tables
Revises: add_channel_specific_templates
Create Date: 2025-08-04 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import uuid

# revision identifiers, used by Alembic.
revision = 'add_payment_gateway_tables'
down_revision = 'add_channel_specific_templates'
branch_labels = None
depends_on = None


def upgrade():
    # Create payment gateway enum
    op.execute("""
        CREATE TYPE payment_gateway AS ENUM (
            'stripe', 'square', 'paypal', 'cash', 'manual'
        );
    """)
    
    # Create payment status enum
    op.execute("""
        CREATE TYPE payment_status AS ENUM (
            'pending', 'processing', 'completed', 'failed', 
            'cancelled', 'refunded', 'partially_refunded', 
            'disputed', 'requires_action'
        );
    """)
    
    # Create payment method enum
    op.execute("""
        CREATE TYPE payment_method AS ENUM (
            'card', 'bank_transfer', 'wallet', 'paypal', 
            'cash', 'check', 'gift_card', 'store_credit'
        );
    """)
    
    # Create refund status enum
    op.execute("""
        CREATE TYPE refund_status AS ENUM (
            'pending', 'processing', 'completed', 'failed', 'cancelled'
        );
    """)
    
    # Create payments table
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('payment_id', sa.String(100), nullable=False),
        
        # Order relationship
        sa.Column('order_id', sa.Integer(), nullable=False),
        
        # Payment gateway information
        sa.Column('gateway', postgresql.ENUM('stripe', 'square', 'paypal', 'cash', 'manual', 
                                            name='payment_gateway', create_type=False), nullable=False),
        sa.Column('gateway_payment_id', sa.String(255), nullable=True),
        sa.Column('gateway_customer_id', sa.String(255), nullable=True),
        
        # Payment details
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'completed', 'failed', 
                                           'cancelled', 'refunded', 'partially_refunded', 
                                           'disputed', 'requires_action',
                                           name='payment_status', create_type=False), 
                 nullable=False, server_default='pending'),
        sa.Column('method', postgresql.ENUM('card', 'bank_transfer', 'wallet', 'paypal', 
                                           'cash', 'check', 'gift_card', 'store_credit',
                                           name='payment_method', create_type=False), nullable=True),
        
        # Customer information
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_name', sa.String(255), nullable=True),
        
        # Payment method details
        sa.Column('payment_method_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        
        # Transaction details
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('statement_descriptor', sa.String(255), nullable=True),
        
        # Processing information
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('fee_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('net_amount', sa.Numeric(10, 2), nullable=True),
        
        # Error handling
        sa.Column('failure_code', sa.String(50), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Idempotency
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('payment_id'),
        sa.UniqueConstraint('idempotency_key'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
    )
    
    # Create indexes for payments
    op.create_index('idx_payment_order_status', 'payments', ['order_id', 'status'])
    op.create_index('idx_payment_gateway_id', 'payments', ['gateway', 'gateway_payment_id'])
    op.create_index('idx_payment_customer', 'payments', ['customer_id', 'status'])
    
    # Create refunds table
    op.create_table(
        'refunds',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('refund_id', sa.String(100), nullable=False),
        
        # Payment relationship
        sa.Column('payment_id', sa.Integer(), nullable=False),
        
        # Gateway information
        sa.Column('gateway', postgresql.ENUM('stripe', 'square', 'paypal', 'cash', 'manual',
                                            name='payment_gateway', create_type=False), nullable=False),
        sa.Column('gateway_refund_id', sa.String(255), nullable=True),
        
        # Refund details
        sa.Column('amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('status', postgresql.ENUM('pending', 'processing', 'completed', 'failed', 'cancelled',
                                           name='refund_status', create_type=False), 
                 nullable=False, server_default='pending'),
        sa.Column('reason', sa.Text(), nullable=True),
        
        # Processing information
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('fee_refunded', sa.Numeric(10, 2), nullable=True),
        
        # Error handling
        sa.Column('failure_code', sa.String(50), nullable=True),
        sa.Column('failure_message', sa.Text(), nullable=True),
        
        # Metadata
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Who initiated the refund
        sa.Column('initiated_by', sa.Integer(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('refund_id'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['initiated_by'], ['users.id']),
    )
    
    # Create indexes for refunds
    op.create_index('idx_refund_payment', 'refunds', ['payment_id'])
    op.create_index('idx_refund_gateway_id', 'refunds', ['gateway', 'gateway_refund_id'])
    op.create_index('idx_refund_status', 'refunds', ['status'])
    
    # Create payment webhooks table
    op.create_table(
        'payment_webhooks',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('webhook_id', sa.String(100), nullable=False),
        
        # Gateway information
        sa.Column('gateway', postgresql.ENUM('stripe', 'square', 'paypal', 'cash', 'manual',
                                            name='payment_gateway', create_type=False), nullable=False),
        sa.Column('gateway_event_id', sa.String(255), nullable=True),
        
        # Event details
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        
        # Webhook data
        sa.Column('headers', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        
        # Processing
        sa.Column('processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('webhook_id'),
        sa.UniqueConstraint('gateway_event_id'),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
    )
    
    # Create indexes for webhooks
    op.create_index('idx_webhook_gateway_event', 'payment_webhooks', ['gateway', 'event_type', 'processed'])
    op.create_index('idx_webhook_payment', 'payment_webhooks', ['payment_id'])
    
    # Create payment gateway config table
    op.create_table(
        'payment_gateway_configs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('gateway', postgresql.ENUM('stripe', 'square', 'paypal', 'cash', 'manual',
                                            name='payment_gateway', create_type=False), nullable=False),
        
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_test_mode', sa.Boolean(), nullable=False, server_default='true'),
        
        # Configuration (should be encrypted in production)
        sa.Column('config', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        
        # Supported features
        sa.Column('supports_refunds', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('supports_partial_refunds', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('supports_recurring', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('supports_save_card', sa.Boolean(), nullable=False, server_default='true'),
        
        # Fee structure
        sa.Column('fee_percentage', sa.Numeric(5, 2), nullable=True),
        sa.Column('fee_fixed', sa.Numeric(10, 2), nullable=True),
        
        # Webhook configuration
        sa.Column('webhook_url', sa.String(500), nullable=True),
        sa.Column('webhook_events', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='[]'),
        
        # Metadata
        sa.Column('description', sa.Text(), nullable=True),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('gateway'),
    )
    
    # Create index for gateway config
    op.create_index('idx_gateway_config_active', 'payment_gateway_configs', ['gateway', 'is_active'])
    
    # Create customer payment methods table
    op.create_table(
        'customer_payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # Customer relationship
        sa.Column('customer_id', sa.Integer(), nullable=False),
        
        # Gateway information
        sa.Column('gateway', postgresql.ENUM('stripe', 'square', 'paypal', 'cash', 'manual',
                                            name='payment_gateway', create_type=False), nullable=False),
        sa.Column('gateway_payment_method_id', sa.String(255), nullable=False),
        sa.Column('gateway_customer_id', sa.String(255), nullable=False),
        
        # Payment method details
        sa.Column('method_type', postgresql.ENUM('card', 'bank_transfer', 'wallet', 'paypal', 
                                                'cash', 'check', 'gift_card', 'store_credit',
                                                name='payment_method', create_type=False), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        
        # Card details (if applicable)
        sa.Column('card_last4', sa.String(4), nullable=True),
        sa.Column('card_brand', sa.String(50), nullable=True),
        sa.Column('card_exp_month', sa.Integer(), nullable=True),
        sa.Column('card_exp_year', sa.Integer(), nullable=True),
        
        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        
        # Metadata
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('customer_id', 'gateway', 'gateway_payment_method_id', 
                           name='uq_customer_gateway_method'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
    )
    
    # Create indexes for customer payment methods
    op.create_index('idx_customer_payment_method', 'customer_payment_methods', ['customer_id', 'is_active'])
    
    # Add payment columns to orders table if not exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='orders' AND column_name='payment_status') THEN
                ALTER TABLE orders ADD COLUMN payment_status VARCHAR(50) DEFAULT 'pending';
            END IF;
        END $$;
    """)
    
    # Create trigger for updated_at
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)
    
    # Add triggers to all payment tables
    for table in ['payments', 'refunds', 'payment_webhooks', 'payment_gateway_configs', 'customer_payment_methods']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # Insert default gateway configurations
    op.execute("""
        INSERT INTO payment_gateway_configs (gateway, is_active, is_test_mode, config, description)
        VALUES 
        ('stripe', false, true, 
         '{"publishable_key": "pk_test_", "secret_key": "sk_test_", "webhook_secret": "whsec_"}',
         'Stripe payment gateway - configure with your API keys'),
        ('square', false, true,
         '{"application_id": "", "access_token": "", "location_id": "", "webhook_signature_key": ""}',
         'Square payment gateway - configure with your API credentials'),
        ('paypal', false, true,
         '{"client_id": "", "client_secret": "", "webhook_id": ""}',
         'PayPal payment gateway - configure with your API credentials');
    """)


def downgrade():
    # Drop triggers
    for table in ['payments', 'refunds', 'payment_webhooks', 'payment_gateway_configs', 'customer_payment_methods']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column();")
    
    # Drop tables in reverse order
    op.drop_table('customer_payment_methods')
    op.drop_table('payment_gateway_configs')
    op.drop_table('payment_webhooks')
    op.drop_table('refunds')
    op.drop_table('payments')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS refund_status;")
    op.execute("DROP TYPE IF EXISTS payment_method;")
    op.execute("DROP TYPE IF EXISTS payment_status;")
    op.execute("DROP TYPE IF EXISTS payment_gateway;")
    
    # Remove payment_status column from orders if it was added
    op.execute("""
        DO $$ 
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.columns 
                      WHERE table_name='orders' AND column_name='payment_status') THEN
                ALTER TABLE orders DROP COLUMN payment_status;
            END IF;
        END $$;
    """)