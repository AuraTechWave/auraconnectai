"""Add settings UI enhancements

Revision ID: add_settings_ui_enhancements
Revises: 
Create Date: 2025-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import json

# revision identifiers, used by Alembic.
revision = 'add_settings_ui_enhancements'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Add default setting groups and definitions for UI"""
    
    # Insert default setting groups
    op.execute("""
        INSERT INTO setting_groups (name, label, description, category, settings, ui_config, sort_order, is_advanced, created_at, updated_at)
        VALUES 
        -- General Settings
        ('restaurant_info', 'Restaurant Information', 'Basic restaurant details', 'general', 
         '["restaurant_name", "restaurant_address", "restaurant_phone", "restaurant_email", "timezone", "currency", "language"]'::json,
         '{"icon": "restaurant"}'::json, 1, false, NOW(), NOW()),
         
        ('business_hours', 'Business Hours', 'Operating hours and schedule', 'general',
         '["opening_time", "closing_time", "days_of_operation", "holiday_schedule"]'::json,
         '{"icon": "schedule"}'::json, 2, false, NOW(), NOW()),
         
        -- Operations Settings
        ('order_management', 'Order Management', 'Order processing configuration', 'operations',
         '["order_timeout_minutes", "auto_confirm_orders", "order_number_format", "kitchen_display_mode"]'::json,
         '{"icon": "receipt_long"}'::json, 1, false, NOW(), NOW()),
         
        ('table_management', 'Table Management', 'Table and seating configuration', 'operations',
         '["table_turn_time_target", "auto_assign_tables", "reservation_lead_time", "max_party_size"]'::json,
         '{"icon": "table_restaurant"}'::json, 2, false, NOW(), NOW()),
         
        -- Payment Settings
        ('payment_processing', 'Payment Processing', 'Payment methods and processing', 'payment',
         '["accepted_payment_methods", "tip_suggestions", "auto_gratuity_percentage", "auto_gratuity_party_size"]'::json,
         '{"icon": "payment"}'::json, 1, false, NOW(), NOW()),
         
        ('tax_configuration', 'Tax Configuration', 'Tax rates and rules', 'payment',
         '["tax_rate", "tax_inclusive_pricing", "tax_exemptions", "service_charge_percentage"]'::json,
         '{"icon": "receipt"}'::json, 2, false, NOW(), NOW()),
         
        -- Notification Settings
        ('customer_notifications', 'Customer Notifications', 'Customer communication preferences', 'notifications',
         '["order_confirmation_sms", "order_ready_notification", "reservation_reminders", "marketing_emails"]'::json,
         '{"icon": "notifications"}'::json, 1, false, NOW(), NOW()),
         
        ('staff_notifications', 'Staff Notifications', 'Internal notification settings', 'notifications',
         '["new_order_alert", "low_inventory_alert", "staff_schedule_reminders", "daily_summary_email"]'::json,
         '{"icon": "notification_important"}'::json, 2, false, NOW(), NOW()),
         
        -- Security Settings
        ('access_control', 'Access Control', 'Security and access settings', 'security',
         '["password_min_length", "password_require_special", "session_timeout_minutes", "two_factor_auth"]'::json,
         '{"icon": "security"}'::json, 1, false, NOW(), NOW()),
         
        ('audit_logging', 'Audit & Logging', 'System audit and logging configuration', 'security',
         '["enable_audit_log", "log_retention_days", "sensitive_data_masking", "compliance_mode"]'::json,
         '{"icon": "history"}'::json, 2, true, NOW(), NOW()),
         
        -- Feature Flags
        ('feature_toggles', 'Feature Toggles', 'Enable or disable features', 'features',
         '["enable_online_ordering", "enable_loyalty_program", "enable_table_reservations", "enable_inventory_tracking"]'::json,
         '{"icon": "toggle_on"}'::json, 1, false, NOW(), NOW()),
         
        ('advanced_features', 'Advanced Features', 'Advanced feature configuration', 'features',
         '["enable_ai_recommendations", "enable_predictive_analytics", "enable_voice_ordering", "enable_blockchain_receipts"]'::json,
         '{"icon": "auto_awesome"}'::json, 2, true, NOW(), NOW())
        ON CONFLICT (name) DO NOTHING;
    """)
    
    # Insert default setting definitions
    op.execute("""
        INSERT INTO setting_definitions (
            key, category, scope, value_type, label, description, 
            default_value, validation_rules, is_required, ui_config, sort_order,
            is_active, created_at, updated_at
        )
        VALUES 
        -- Restaurant Information
        ('restaurant_name', 'general', 'restaurant', 'string', 'Restaurant Name', 
         'The name of your restaurant', '""', '{"maxLength": 100}'::json, true,
         '{"placeholder": "Enter restaurant name"}'::json, 1, true, NOW(), NOW()),
         
        ('restaurant_address', 'general', 'restaurant', 'string', 'Address', 
         'Physical address of the restaurant', '""', '{"maxLength": 200}'::json, true,
         '{"placeholder": "123 Main St, City, State ZIP"}'::json, 2, true, NOW(), NOW()),
         
        ('restaurant_phone', 'general', 'restaurant', 'string', 'Phone Number', 
         'Main contact phone number', '""', '{"pattern": "^\\\\+?[0-9\\\\s\\\\-\\\\(\\\\)]+$"}'::json, true,
         '{"placeholder": "(555) 123-4567", "prefix": "📞"}'::json, 3, true, NOW(), NOW()),
         
        ('timezone', 'general', 'restaurant', 'enum', 'Time Zone', 
         'Restaurant timezone for operations', '"America/New_York"', '{}', true,
         '{"placeholder": "Select timezone"}'::json, 4, true, NOW(), NOW()),
         
        ('currency', 'general', 'restaurant', 'enum', 'Currency', 
         'Default currency for transactions', '"USD"', '{}', true,
         '{"placeholder": "Select currency"}'::json, 5, true, NOW(), NOW()),
         
        -- Order Management
        ('order_timeout_minutes', 'operations', 'restaurant', 'integer', 'Order Timeout', 
         'Minutes before an order times out', '60', '{"min": 15, "max": 240}'::json, true,
         '{"suffix": "minutes", "step": 15}'::json, 1, true, NOW(), NOW()),
         
        ('auto_confirm_orders', 'operations', 'restaurant', 'boolean', 'Auto-Confirm Orders', 
         'Automatically confirm new orders', 'false', '{}', false,
         '{"helpText": "Enable to skip manual confirmation step"}'::json, 2, true, NOW(), NOW()),
         
        ('table_turn_time_target', 'operations', 'restaurant', 'integer', 'Target Table Turn Time', 
         'Target minutes for table turnover', '60', '{"min": 15, "max": 180}'::json, false,
         '{"suffix": "minutes", "helpText": "Used for analytics and alerts"}'::json, 3, true, NOW(), NOW()),
         
        -- Payment Settings
        ('tax_rate', 'payment', 'restaurant', 'float', 'Sales Tax Rate', 
         'Default sales tax percentage', '8.5', '{"min": 0, "max": 30}'::json, true,
         '{"suffix": "%", "step": 0.1}'::json, 1, true, NOW(), NOW()),
         
        ('tip_suggestions', 'payment', 'restaurant', 'json', 'Tip Suggestions', 
         'Suggested tip percentages', '[15, 18, 20, 25]', '{}', false,
         '{"helpText": "Percentages shown to customers"}'::json, 2, true, NOW(), NOW()),
         
        -- Notifications
        ('order_confirmation_sms', 'notifications', 'restaurant', 'boolean', 'Order Confirmation SMS', 
         'Send SMS confirmation for orders', 'true', '{}', false,
         '{"helpText": "Requires SMS service configuration"}'::json, 1, true, NOW(), NOW()),
         
        ('low_inventory_alert', 'notifications', 'restaurant', 'boolean', 'Low Inventory Alerts', 
         'Alert when inventory is low', 'true', '{}', false,
         '{"helpText": "Sends notifications to managers"}'::json, 2, true, NOW(), NOW()),
         
        -- Security
        ('password_min_length', 'security', 'system', 'integer', 'Minimum Password Length', 
         'Minimum required password length', '8', '{"min": 6, "max": 32}'::json, true,
         '{"suffix": "characters"}'::json, 1, true, NOW(), NOW()),
         
        ('session_timeout_minutes', 'security', 'restaurant', 'integer', 'Session Timeout', 
         'Minutes before session expires', '30', '{"min": 5, "max": 480}'::json, true,
         '{"suffix": "minutes", "helpText": "For security compliance"}'::json, 2, true, NOW(), NOW()),
         
        -- Features
        ('enable_online_ordering', 'features', 'restaurant', 'boolean', 'Online Ordering', 
         'Enable online ordering system', 'true', '{}', false,
         '{"helpText": "Allow customers to place orders online"}'::json, 1, true, NOW(), NOW()),
         
        ('enable_loyalty_program', 'features', 'restaurant', 'boolean', 'Loyalty Program', 
         'Enable customer loyalty rewards', 'false', '{}', false,
         '{"helpText": "Track points and rewards for customers"}'::json, 2, true, NOW(), NOW())
        ON CONFLICT (key) DO NOTHING;
    """)
    
    # Update allowed values for enum types
    op.execute("""
        UPDATE setting_definitions 
        SET allowed_values = '["USD", "EUR", "GBP", "CAD", "AUD", "JPY"]'::json
        WHERE key = 'currency';
        
        UPDATE setting_definitions 
        SET allowed_values = '["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Phoenix", "Europe/London", "Europe/Paris", "Asia/Tokyo", "Australia/Sydney"]'::json
        WHERE key = 'timezone';
    """)
    
    # Add indexes for performance
    op.create_index('idx_settings_ui_lookup', 'settings', ['key', 'scope', 'restaurant_id', 'is_active'])
    op.create_index('idx_setting_groups_category', 'setting_groups', ['category', 'sort_order'])
    

def downgrade():
    """Remove UI enhancements"""
    
    # Remove indexes
    op.drop_index('idx_settings_ui_lookup', 'settings')
    op.drop_index('idx_setting_groups_category', 'setting_groups')
    
    # Remove default data (optional - depends on requirements)
    op.execute("""
        DELETE FROM setting_groups 
        WHERE name IN (
            'restaurant_info', 'business_hours', 'order_management', 'table_management',
            'payment_processing', 'tax_configuration', 'customer_notifications',
            'staff_notifications', 'access_control', 'audit_logging',
            'feature_toggles', 'advanced_features'
        );
    """)
    
    op.execute("""
        DELETE FROM setting_definitions 
        WHERE key IN (
            'restaurant_name', 'restaurant_address', 'restaurant_phone', 'timezone', 'currency',
            'order_timeout_minutes', 'auto_confirm_orders', 'table_turn_time_target',
            'tax_rate', 'tip_suggestions', 'order_confirmation_sms', 'low_inventory_alert',
            'password_min_length', 'session_timeout_minutes', 'enable_online_ordering',
            'enable_loyalty_program'
        );
    """)