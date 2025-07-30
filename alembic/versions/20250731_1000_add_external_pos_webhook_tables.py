"""Add external POS webhook tables

Revision ID: 20250731_1000_add_external_pos_webhook_tables
Revises: 20250730_1000_add_order_sync_tables
Create Date: 2025-07-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250731_1000_add_external_pos_webhook_tables'
down_revision = '20250729_1900_add_feedback_and_reviews_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create external_pos_providers table
    op.create_table(
        'external_pos_providers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_code', sa.String(50), nullable=False),
        sa.Column('provider_name', sa.String(100), nullable=False),
        sa.Column('webhook_endpoint_id', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('auth_type', sa.String(50), nullable=False),
        sa.Column('auth_config', postgresql.JSONB(), nullable=False),
        sa.Column('settings', postgresql.JSONB(), nullable=True),
        sa.Column('supported_events', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True, server_default='60'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_code'),
        sa.UniqueConstraint('webhook_endpoint_id')
    )
    op.create_index('idx_external_pos_providers_active', 'external_pos_providers', ['is_active'])
    op.create_index('idx_external_pos_providers_code', 'external_pos_providers', ['provider_code'])
    
    # Create external_pos_webhook_events table
    op.create_table(
        'external_pos_webhook_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(), nullable=False),
        sa.Column('request_headers', postgresql.JSONB(), nullable=False),
        sa.Column('request_body', postgresql.JSONB(), nullable=False),
        sa.Column('request_signature', sa.String(500), nullable=True),
        sa.Column('processing_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verification_details', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['provider_id'], ['external_pos_providers.id'], ),
        sa.UniqueConstraint('event_id')
    )
    op.create_index('idx_webhook_event_processing', 'external_pos_webhook_events', ['processing_status', 'created_at'])
    op.create_index('idx_webhook_event_provider_type', 'external_pos_webhook_events', ['provider_id', 'event_type'])
    op.create_index('idx_webhook_event_timestamp', 'external_pos_webhook_events', ['event_timestamp'])
    
    # Create external_pos_payment_updates table
    op.create_table(
        'external_pos_payment_updates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('webhook_event_id', sa.Integer(), nullable=False),
        sa.Column('external_transaction_id', sa.String(200), nullable=False),
        sa.Column('external_order_id', sa.String(200), nullable=True),
        sa.Column('external_payment_id', sa.String(200), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('payment_status', sa.String(50), nullable=False),
        sa.Column('payment_method', sa.String(50), nullable=False),
        sa.Column('payment_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False, server_default='USD'),
        sa.Column('tip_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('tax_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('card_last_four', sa.String(4), nullable=True),
        sa.Column('card_brand', sa.String(50), nullable=True),
        sa.Column('customer_email', sa.String(255), nullable=True),
        sa.Column('customer_phone', sa.String(50), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('processing_notes', sa.Text(), nullable=True),
        sa.Column('raw_payment_data', postgresql.JSONB(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['webhook_event_id'], ['external_pos_webhook_events.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], )
    )
    op.create_index('idx_payment_update_external_refs', 'external_pos_payment_updates', ['external_transaction_id', 'external_order_id'])
    op.create_index('idx_payment_update_processing', 'external_pos_payment_updates', ['is_processed', 'created_at'])
    op.create_index('idx_payment_update_webhook_event', 'external_pos_payment_updates', ['webhook_event_id'])
    op.create_index('idx_payment_update_order', 'external_pos_payment_updates', ['order_id'])
    
    # Create external_pos_webhook_logs table
    op.create_table(
        'external_pos_webhook_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('webhook_event_id', sa.Integer(), nullable=False),
        sa.Column('log_level', sa.String(20), nullable=False),
        sa.Column('log_type', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', postgresql.JSONB(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['webhook_event_id'], ['external_pos_webhook_events.id'], )
    )
    op.create_index('idx_webhook_log_event', 'external_pos_webhook_logs', ['webhook_event_id', 'occurred_at'])
    
    # Add payment-related columns to orders table if they don't exist
    # Check if columns exist first to avoid errors
    op.add_column('orders', sa.Column('payment_status', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('external_payment_id', sa.String(200), nullable=True))
    op.add_column('orders', sa.Column('payment_method', sa.String(50), nullable=True))
    op.add_column('orders', sa.Column('total_amount', sa.Numeric(10, 2), nullable=True))
    
    # Create indexes on new order columns
    op.create_index('idx_orders_payment_status', 'orders', ['payment_status'])
    op.create_index('idx_orders_external_payment_id', 'orders', ['external_payment_id'])
    
    # Insert default providers
    op.execute("""
        INSERT INTO external_pos_providers (provider_code, provider_name, webhook_endpoint_id, auth_type, auth_config, supported_events) VALUES
        ('square', 'Square', 'square-webhook', 'hmac_sha256', '{"webhook_secret": "", "signature_header": "X-Square-Signature"}', '["payment.updated", "payment.created"]'),
        ('stripe', 'Stripe', 'stripe-webhook', 'hmac_sha256', '{"webhook_secret": "", "signature_header": "Stripe-Signature"}', '["payment_intent.succeeded", "payment_intent.payment_failed"]'),
        ('toast', 'Toast', 'toast-webhook', 'api_key', '{"api_key": "", "api_key_header": "X-Toast-API-Key"}', '["payment.completed", "payment.voided"]'),
        ('clover', 'Clover', 'clover-webhook', 'api_key', '{"api_key": "", "api_key_header": "X-Clover-API-Key"}', '["payment.processed", "payment.refunded"]')
        ON CONFLICT (provider_code) DO NOTHING
    """)


def downgrade():
    # Drop indexes on orders table
    op.drop_index('idx_orders_external_payment_id', 'orders')
    op.drop_index('idx_orders_payment_status', 'orders')
    
    # Remove columns from orders table
    op.drop_column('orders', 'total_amount')
    op.drop_column('orders', 'payment_method')
    op.drop_column('orders', 'external_payment_id')
    op.drop_column('orders', 'payment_status')
    
    # Drop tables in reverse order
    op.drop_table('external_pos_webhook_logs')
    op.drop_table('external_pos_payment_updates')
    op.drop_table('external_pos_webhook_events')
    op.drop_table('external_pos_providers')