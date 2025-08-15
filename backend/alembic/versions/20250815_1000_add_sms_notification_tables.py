"""Add SMS notification tables

Revision ID: add_sms_notification_tables
Revises: 20250814_fix_customer_lifetime_value
Create Date: 2025-08-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_sms_notification_tables'
down_revision = '20250814_fix_customer_lifetime_value'
branch_labels = None
depends_on = None


def upgrade():
    # Create SMS provider enum
    op.execute("CREATE TYPE smsprovider AS ENUM ('twilio', 'aws_sns', 'sendgrid', 'messagebird')")
    op.execute("CREATE TYPE smsstatus AS ENUM ('queued', 'sending', 'sent', 'delivered', 'failed', 'undelivered', 'bounced')")
    op.execute("CREATE TYPE smsdirection AS ENUM ('outbound', 'inbound')")
    op.execute("CREATE TYPE smstemplatecategory AS ENUM ('reservation', 'order', 'marketing', 'authentication', 'notification', 'reminder', 'alert')")
    
    # Create sms_templates table
    op.create_table('sms_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('category', postgresql.ENUM('reservation', 'order', 'marketing', 'authentication', 'notification', 'reminder', 'alert', name='smstemplatecategory'), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_body', sa.Text(), nullable=False),
        sa.Column('variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('max_length', sa.Integer(), nullable=True, server_default='160'),
        sa.Column('estimated_segments', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('usage_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('parent_template_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['parent_template_id'], ['sms_templates.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_sms_templates_category', 'sms_templates', ['category'])
    
    # Add check constraints
    op.create_check_constraint(
        'check_max_length_positive',
        'sms_templates',
        'max_length > 0'
    )
    op.create_check_constraint(
        'check_segments_positive',
        'sms_templates',
        'estimated_segments > 0'
    )
    
    # Create sms_messages table
    op.create_table('sms_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', postgresql.ENUM('twilio', 'aws_sns', 'sendgrid', 'messagebird', name='smsprovider'), nullable=False, server_default='twilio'),
        sa.Column('direction', postgresql.ENUM('outbound', 'inbound', name='smsdirection'), nullable=False, server_default='outbound'),
        sa.Column('status', postgresql.ENUM('queued', 'sending', 'sent', 'delivered', 'failed', 'undelivered', 'bounced', name='smsstatus'), nullable=False, server_default='queued'),
        sa.Column('from_number', sa.String(20), nullable=False),
        sa.Column('to_number', sa.String(20), nullable=False),
        sa.Column('message_body', sa.Text(), nullable=False),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('template_variables', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('provider_message_id', sa.String(255), nullable=True),
        sa.Column('provider_response', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('provider_error', sa.Text(), nullable=True),
        sa.Column('segments_count', sa.Integer(), nullable=True, server_default='1'),
        sa.Column('cost_amount', sa.Float(), nullable=True),
        sa.Column('cost_currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('reservation_id', sa.Integer(), nullable=True),
        sa.Column('staff_id', sa.Integer(), nullable=True),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['template_id'], ['sms_templates.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.UniqueConstraint('provider_message_id')
    )
    
    # Create indexes for sms_messages
    op.create_index('idx_sms_messages_to_number', 'sms_messages', ['to_number'])
    op.create_index('idx_sms_messages_provider_message_id', 'sms_messages', ['provider_message_id'])
    op.create_index('idx_sms_messages_customer_id', 'sms_messages', ['customer_id'])
    op.create_index('idx_sms_messages_status_created', 'sms_messages', ['status', 'created_at'])
    op.create_index('idx_sms_messages_customer_created', 'sms_messages', ['customer_id', 'created_at'])
    op.create_index('idx_sms_messages_provider_status', 'sms_messages', ['provider', 'status'])
    
    # Create sms_opt_outs table
    op.create_table('sms_opt_outs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('phone_number', sa.String(20), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('opted_out', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('opt_out_date', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('opt_out_reason', sa.String(255), nullable=True),
        sa.Column('opt_out_method', sa.String(50), nullable=True),
        sa.Column('opted_in_date', sa.DateTime(), nullable=True),
        sa.Column('opt_in_method', sa.String(50), nullable=True),
        sa.Column('categories_opted_out', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('compliance_notes', sa.Text(), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.UniqueConstraint('phone_number')
    )
    
    # Create indexes for sms_opt_outs
    op.create_index('idx_sms_opt_outs_phone_number', 'sms_opt_outs', ['phone_number'])
    op.create_index('idx_sms_opt_outs_customer_id', 'sms_opt_outs', ['customer_id'])
    op.create_index('idx_opt_out_customer', 'sms_opt_outs', ['customer_id', 'opted_out'])
    op.create_index('idx_opt_out_date', 'sms_opt_outs', ['opt_out_date'])
    
    # Create sms_costs table
    op.create_table('sms_costs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('billing_period_start', sa.DateTime(), nullable=False),
        sa.Column('billing_period_end', sa.DateTime(), nullable=False),
        sa.Column('provider', postgresql.ENUM('twilio', 'aws_sns', 'sendgrid', 'messagebird', name='smsprovider'), nullable=False),
        sa.Column('total_messages', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('total_segments', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('outbound_cost', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('inbound_cost', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('phone_number_cost', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('additional_fees', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('total_cost', sa.Float(), nullable=True, server_default='0.0'),
        sa.Column('currency', sa.String(3), nullable=True, server_default='USD'),
        sa.Column('cost_by_category', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('provider_invoice_id', sa.String(255), nullable=True),
        sa.Column('provider_invoice_url', sa.String(500), nullable=True),
        sa.Column('is_paid', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('payment_reference', sa.String(255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.UniqueConstraint('provider', 'billing_period_start', 'billing_period_end', name='unique_provider_billing_period')
    )
    
    # Create indexes for sms_costs
    op.create_index('idx_sms_cost_period', 'sms_costs', ['billing_period_start', 'billing_period_end'])
    op.create_index('idx_sms_cost_provider_period', 'sms_costs', ['provider', 'billing_period_start'])


def downgrade():
    # Drop tables
    op.drop_table('sms_costs')
    op.drop_table('sms_opt_outs')
    op.drop_table('sms_messages')
    op.drop_table('sms_templates')
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS smstemplatecategory")
    op.execute("DROP TYPE IF EXISTS smsdirection")
    op.execute("DROP TYPE IF EXISTS smsstatus")
    op.execute("DROP TYPE IF EXISTS smsprovider")