"""Add order tracking tables

Revision ID: add_order_tracking_tables
Revises: 20250802_1700_add_recipe_management
Create Date: 2025-08-03 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_order_tracking_tables'
down_revision = 'add_recipe_management'
branch_labels = None
depends_on = None


def upgrade():
    # Create enum types
    op.execute("""
        CREATE TYPE trackingeventtype AS ENUM (
            'order_placed', 'order_confirmed', 'order_in_kitchen', 
            'order_being_prepared', 'order_ready', 'order_served', 
            'order_completed', 'order_cancelled', 'order_delayed',
            'order_picked_up', 'order_out_for_delivery', 'order_delivered',
            'payment_received', 'custom_event'
        )
    """)
    
    op.execute("""
        CREATE TYPE notificationchannel AS ENUM (
            'push', 'email', 'sms', 'in_app', 'webhook'
        )
    """)

    # Create order_tracking_events table
    op.create_table(
        'order_tracking_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('event_type', postgresql.ENUM('order_placed', 'order_confirmed', 'order_in_kitchen', 
                                                'order_being_prepared', 'order_ready', 'order_served', 
                                                'order_completed', 'order_cancelled', 'order_delayed',
                                                'order_picked_up', 'order_out_for_delivery', 'order_delivered',
                                                'payment_received', 'custom_event', 
                                                name='trackingeventtype', create_type=False), nullable=False),
        sa.Column('old_status', sa.String(), nullable=True),
        sa.Column('new_status', sa.String(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('location_accuracy', sa.Float(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('triggered_by_type', sa.String(), nullable=False, server_default='system'),
        sa.Column('triggered_by_id', sa.Integer(), nullable=True),
        sa.Column('triggered_by_name', sa.String(), nullable=True),
        sa.Column('estimated_completion_time', sa.DateTime(), nullable=True),
        sa.Column('actual_completion_time', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_order_tracking_order_created', 'order_tracking_events', ['order_id', 'created_at'])
    op.create_index('idx_order_tracking_event_type', 'order_tracking_events', ['event_type', 'created_at'])

    # Create customer_order_tracking table
    op.create_table(
        'customer_order_tracking',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('tracking_code', sa.String(20), nullable=False),
        sa.Column('tracking_url', sa.String(), nullable=True),
        sa.Column('access_token', sa.String(), nullable=True),
        sa.Column('enable_push', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('enable_email', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('enable_sms', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('notification_email', sa.String(), nullable=True),
        sa.Column('notification_phone', sa.String(), nullable=True),
        sa.Column('push_token', sa.String(), nullable=True),
        sa.Column('last_accessed_at', sa.DateTime(), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('websocket_connected', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.Column('websocket_session_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('order_id'),
        sa.UniqueConstraint('tracking_code'),
        sa.UniqueConstraint('access_token')
    )
    op.create_index(op.f('ix_customer_order_tracking_order_id'), 'customer_order_tracking', ['order_id'])
    op.create_index(op.f('ix_customer_order_tracking_customer_id'), 'customer_order_tracking', ['customer_id'])
    op.create_index(op.f('ix_customer_order_tracking_tracking_code'), 'customer_order_tracking', ['tracking_code'])
    op.create_index(op.f('ix_customer_order_tracking_access_token'), 'customer_order_tracking', ['access_token'])

    # Create order_notifications table
    op.create_table(
        'order_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('tracking_event_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('channel', postgresql.ENUM('push', 'email', 'sms', 'in_app', 'webhook',
                                            name='notificationchannel', create_type=False), nullable=False),
        sa.Column('recipient', sa.String(), nullable=False),
        sa.Column('subject', sa.String(), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('external_id', sa.String(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tracking_event_id'], ['order_tracking_events.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_order_notifications_order_channel', 'order_notifications', ['order_id', 'channel'])
    op.create_index('idx_order_notifications_sent_at', 'order_notifications', ['sent_at'])

    # Create order_tracking_templates table
    op.create_table(
        'order_tracking_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_type', postgresql.ENUM('order_placed', 'order_confirmed', 'order_in_kitchen', 
                                                'order_being_prepared', 'order_ready', 'order_served', 
                                                'order_completed', 'order_cancelled', 'order_delayed',
                                                'order_picked_up', 'order_out_for_delivery', 'order_delivered',
                                                'payment_received', 'custom_event',
                                                name='trackingeventtype', create_type=False), nullable=False),
        sa.Column('channel', postgresql.ENUM('push', 'email', 'sms', 'in_app', 'webhook',
                                            name='notificationchannel', create_type=False), nullable=False),
        sa.Column('language', sa.String(5), nullable=False, server_default='en'),
        sa.Column('subject_template', sa.String(), nullable=True),
        sa.Column('message_template', sa.Text(), nullable=False),
        sa.Column('available_variables', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.true()),
        sa.Column('priority', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_tracking_template_lookup', 'order_tracking_templates', 
                    ['event_type', 'channel', 'language', 'is_active'])

    # Insert default templates
    op.execute("""
        INSERT INTO order_tracking_templates (event_type, channel, language, subject_template, message_template, available_variables, created_at, updated_at)
        VALUES 
        ('order_placed', 'email', 'en', 'Order #{order_id} Confirmed', 
         'Thank you for your order! Your order #{order_id} has been placed and is being processed. Estimated completion time: {estimated_time}', 
         '{"order_id": "Order ID", "estimated_time": "Estimated completion time", "customer_name": "Customer name"}', NOW(), NOW()),
        
        ('order_ready', 'push', 'en', 'Order Ready!', 
         'Your order #{order_id} is ready for pickup!', 
         '{"order_id": "Order ID"}', NOW(), NOW()),
        
        ('order_ready', 'sms', 'en', NULL, 
         'Your order #{order_id} is ready for pickup at the restaurant.', 
         '{"order_id": "Order ID"}', NOW(), NOW()),
        
        ('order_out_for_delivery', 'push', 'en', 'Order On The Way!', 
         'Your order #{order_id} is out for delivery. Track your driver in real-time!', 
         '{"order_id": "Order ID"}', NOW(), NOW()),
        
        ('order_delivered', 'email', 'en', 'Order #{order_id} Delivered', 
         'Your order has been delivered. We hope you enjoy your meal! Please rate your experience.', 
         '{"order_id": "Order ID"}', NOW(), NOW())
    """)


def downgrade():
    # Drop tables in reverse order due to foreign key constraints
    op.drop_index('idx_tracking_template_lookup', table_name='order_tracking_templates')
    op.drop_table('order_tracking_templates')
    
    op.drop_index('idx_order_notifications_sent_at', table_name='order_notifications')
    op.drop_index('idx_order_notifications_order_channel', table_name='order_notifications')
    op.drop_table('order_notifications')
    
    op.drop_index(op.f('ix_customer_order_tracking_access_token'), table_name='customer_order_tracking')
    op.drop_index(op.f('ix_customer_order_tracking_tracking_code'), table_name='customer_order_tracking')
    op.drop_index(op.f('ix_customer_order_tracking_customer_id'), table_name='customer_order_tracking')
    op.drop_index(op.f('ix_customer_order_tracking_order_id'), table_name='customer_order_tracking')
    op.drop_table('customer_order_tracking')
    
    op.drop_index('idx_order_tracking_event_type', table_name='order_tracking_events')
    op.drop_index('idx_order_tracking_order_created', table_name='order_tracking_events')
    op.drop_table('order_tracking_events')
    
    # Drop enum types
    op.execute('DROP TYPE notificationchannel')
    op.execute('DROP TYPE trackingeventtype')