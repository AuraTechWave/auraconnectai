"""add email notification system

Revision ID: 20250822_add_email_notification_system
Revises: 
Create Date: 2025-08-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250822_add_email_notification_system'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create email_templates table
    op.create_table('email_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.Enum('reservation', 'order', 'marketing', 'authentication', 
                                     'notification', 'reminder', 'alert', 'invoice', 'receipt', 
                                     name='emailtemplatecategory'), nullable=False),
        sa.Column('subject_template', sa.String(length=500), nullable=False),
        sa.Column('html_body_template', sa.Text(), nullable=False),
        sa.Column('text_body_template', sa.Text(), nullable=True),
        sa.Column('sendgrid_template_id', sa.String(length=255), nullable=True),
        sa.Column('ses_template_name', sa.String(length=255), nullable=True),
        sa.Column('variables', sa.JSON(), nullable=True),
        sa.Column('default_values', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_transactional', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index('idx_email_templates_active', 'email_templates', ['is_active'], unique=False)
    op.create_index('idx_email_templates_category', 'email_templates', ['category'], unique=False)

    # Create email_messages table
    op.create_table('email_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.Enum('sendgrid', 'aws_ses', 'mailgun', 'smtp', name='emailprovider'), 
                  nullable=False, server_default='sendgrid'),
        sa.Column('direction', sa.Enum('outbound', 'inbound', name='emaildirection'), 
                  nullable=False, server_default='outbound'),
        sa.Column('status', sa.Enum('queued', 'sending', 'sent', 'delivered', 'failed', 'bounced', 
                                   'complained', 'opened', 'clicked', name='emailstatus'), 
                  nullable=False, server_default='queued'),
        sa.Column('from_email', sa.String(length=255), nullable=False),
        sa.Column('from_name', sa.String(length=255), nullable=True),
        sa.Column('to_email', sa.String(length=255), nullable=False),
        sa.Column('to_name', sa.String(length=255), nullable=True),
        sa.Column('cc_emails', sa.JSON(), nullable=True),
        sa.Column('bcc_emails', sa.JSON(), nullable=True),
        sa.Column('reply_to_email', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=False),
        sa.Column('html_body', sa.Text(), nullable=True),
        sa.Column('text_body', sa.Text(), nullable=True),
        sa.Column('template_id', sa.Integer(), nullable=True),
        sa.Column('template_variables', sa.JSON(), nullable=True),
        sa.Column('provider_message_id', sa.String(length=255), nullable=True),
        sa.Column('provider_response', sa.JSON(), nullable=True),
        sa.Column('provider_error', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('clicked_at', sa.DateTime(), nullable=True),
        sa.Column('bounced_at', sa.DateTime(), nullable=True),
        sa.Column('complained_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('order_id', sa.Integer(), nullable=True),
        sa.Column('reservation_id', sa.Integer(), nullable=True),
        sa.Column('staff_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ),
        sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], ),
        sa.ForeignKeyConstraint(['staff_id'], ['staff.id'], ),
        sa.ForeignKeyConstraint(['template_id'], ['email_templates.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_message_id')
    )
    op.create_index('idx_email_messages_customer', 'email_messages', ['customer_id', 'created_at'], unique=False)
    op.create_index('idx_email_messages_retry', 'email_messages', ['next_retry_at', 'status'], unique=False)
    op.create_index('idx_email_messages_scheduled', 'email_messages', ['scheduled_at', 'status'], unique=False)
    op.create_index('idx_email_messages_status', 'email_messages', ['status'], unique=False)
    op.create_index('idx_email_messages_to_email', 'email_messages', ['to_email'], unique=False)

    # Create email_attachments table
    op.create_table('email_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_message_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('content_id', sa.String(length=255), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('storage_path', sa.String(length=500), nullable=True),
        sa.Column('content_base64', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['email_message_id'], ['email_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create email_unsubscribes table
    op.create_table('email_unsubscribes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('unsubscribe_all', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('unsubscribed_categories', sa.JSON(), nullable=True),
        sa.Column('unsubscribed_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('unsubscribe_token', sa.String(length=255), nullable=True),
        sa.Column('unsubscribe_reason', sa.Text(), nullable=True),
        sa.Column('resubscribed_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('unsubscribe_token')
    )
    op.create_index('idx_email_unsubscribes_email', 'email_unsubscribes', ['email'], unique=True)

    # Create email_bounces table
    op.create_table('email_bounces',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('email_message_id', sa.Integer(), nullable=True),
        sa.Column('bounce_type', sa.String(length=50), nullable=False),
        sa.Column('bounce_subtype', sa.String(length=50), nullable=True),
        sa.Column('provider', sa.Enum('sendgrid', 'aws_ses', 'mailgun', 'smtp', name='emailprovider'), nullable=False),
        sa.Column('provider_response', sa.JSON(), nullable=True),
        sa.Column('diagnostic_code', sa.Text(), nullable=True),
        sa.Column('is_permanent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('retry_count', sa.Integer(), server_default='0'),
        sa.Column('bounced_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['email_message_id'], ['email_messages.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_email_bounces_email', 'email_bounces', ['email', 'is_permanent'], unique=False)
    op.create_index('idx_email_bounces_type', 'email_bounces', ['bounce_type'], unique=False)


def downgrade():
    # Drop tables in reverse order
    op.drop_index('idx_email_bounces_type', table_name='email_bounces')
    op.drop_index('idx_email_bounces_email', table_name='email_bounces')
    op.drop_table('email_bounces')
    
    op.drop_index('idx_email_unsubscribes_email', table_name='email_unsubscribes')
    op.drop_table('email_unsubscribes')
    
    op.drop_table('email_attachments')
    
    op.drop_index('idx_email_messages_to_email', table_name='email_messages')
    op.drop_index('idx_email_messages_status', table_name='email_messages')
    op.drop_index('idx_email_messages_scheduled', table_name='email_messages')
    op.drop_index('idx_email_messages_retry', table_name='email_messages')
    op.drop_index('idx_email_messages_customer', table_name='email_messages')
    op.drop_table('email_messages')
    
    op.drop_index('idx_email_templates_category', table_name='email_templates')
    op.drop_index('idx_email_templates_active', table_name='email_templates')
    op.drop_table('email_templates')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS emailstatus')
    op.execute('DROP TYPE IF EXISTS emaildirection')
    op.execute('DROP TYPE IF EXISTS emailprovider')
    op.execute('DROP TYPE IF EXISTS emailtemplatecategory')