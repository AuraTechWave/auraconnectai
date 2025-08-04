"""Add channel-specific template columns

Revision ID: add_channel_specific_templates
Revises: add_notification_improvements
Create Date: 2025-08-03 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_channel_specific_templates'
down_revision = 'add_notification_improvements'
branch_labels = None
depends_on = None


def upgrade():
    # Add channel-specific template columns to order_tracking_templates
    op.add_column('order_tracking_templates', 
        sa.Column('push_title_template', sa.String(), nullable=True))
    op.add_column('order_tracking_templates', 
        sa.Column('push_body_template', sa.Text(), nullable=True))
    op.add_column('order_tracking_templates', 
        sa.Column('sms_template', sa.Text(), nullable=True))
    op.add_column('order_tracking_templates', 
        sa.Column('html_template', sa.Text(), nullable=True))
    op.add_column('order_tracking_templates', 
        sa.Column('push_image_url', sa.String(), nullable=True))
    op.add_column('order_tracking_templates', 
        sa.Column('push_action_url', sa.String(), nullable=True))
    op.add_column('order_tracking_templates', 
        sa.Column('channel_settings', postgresql.JSONB(astext_type=sa.Text()), 
                  nullable=True, server_default='{}'))

    # Add GIN index on channel_settings
    op.execute("""
        CREATE INDEX idx_tracking_template_settings_gin 
        ON order_tracking_templates USING GIN (channel_settings);
    """)

    # Insert channel-specific templates
    op.execute("""
        -- Email templates with HTML
        UPDATE order_tracking_templates 
        SET html_template = '<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 0; padding: 0; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background-color: #FF5722; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }
        .content { padding: 20px; background-color: #f5f5f5; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
        .button { background-color: #FF5722; color: white; padding: 12px 24px; text-decoration: none; display: inline-block; margin: 15px 0; border-radius: 4px; }
        .details { background: white; padding: 15px; margin: 15px 0; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Order Update</h1>
        </div>
        <div class="content">
            <p>{message}</p>
            <div class="details">
                <strong>Order #{order_id}</strong><br>
                Status: {status}
            </div>
            <a href="{tracking_url}" class="button">Track Order</a>
        </div>
        <div class="footer">
            <p>© 2025 AuraConnect. All rights reserved.</p>
        </div>
    </div>
</body>
</html>',
        channel_settings = '{"reply_to": "noreply@auraconnect.ai", "category": "order_update"}'::jsonb
        WHERE channel = 'email';

        -- Push notification templates
        INSERT INTO order_tracking_templates (
            event_type, channel, language, 
            subject_template, message_template,
            push_title_template, push_body_template,
            push_image_url, push_action_url,
            channel_settings, is_active, priority,
            created_at, updated_at
        ) VALUES 
        ('order_ready', 'push', 'en',
         'Order Ready!', 'Your order #{order_id} is ready for pickup!',
         'Order Ready! 🍽️', 'Your order #{order_id} is ready!',
         NULL, 'app://orders/{order_id}',
         '{"sound": "order_ready.mp3", "priority": "high", "android_channel_id": "order_ready", "ios_category": "ORDER_READY"}'::jsonb,
         true, 10, NOW(), NOW()),
         
        ('order_out_for_delivery', 'push', 'en',
         'On the way!', 'Your order #{order_id} is out for delivery',
         'Driver on the way! 🚗', 'Track your order #{order_id} in real-time',
         NULL, 'app://orders/{order_id}/track',
         '{"sound": "default", "priority": "high", "android_channel_id": "delivery", "ios_category": "DELIVERY_UPDATE"}'::jsonb,
         true, 10, NOW(), NOW());

        -- SMS templates
        UPDATE order_tracking_templates 
        SET sms_template = 'Order #{order_id} ready! Show code {pickup_code} at pickup.',
            channel_settings = '{"sender_id": "AURACONNECT", "type": "transactional"}'::jsonb
        WHERE channel = 'sms' AND event_type = 'order_ready';

        INSERT INTO order_tracking_templates (
            event_type, channel, language,
            subject_template, message_template, sms_template,
            channel_settings, is_active, priority,
            created_at, updated_at
        ) VALUES
        ('order_delivered', 'sms', 'en',
         NULL, 'Your order has been delivered',
         'Order #{order_id} delivered! Rate your experience: {rating_url}',
         '{"sender_id": "AURACONNECT", "type": "transactional"}'::jsonb,
         true, 5, NOW(), NOW());
    """)


def downgrade():
    # Drop GIN index
    op.execute("DROP INDEX IF EXISTS idx_tracking_template_settings_gin")
    
    # Drop columns
    op.drop_column('order_tracking_templates', 'channel_settings')
    op.drop_column('order_tracking_templates', 'push_action_url')
    op.drop_column('order_tracking_templates', 'push_image_url')
    op.drop_column('order_tracking_templates', 'html_template')
    op.drop_column('order_tracking_templates', 'sms_template')
    op.drop_column('order_tracking_templates', 'push_body_template')
    op.drop_column('order_tracking_templates', 'push_title_template')