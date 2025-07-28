"""Add comprehensive customer system

Revision ID: 005_add_customer_system
Revises: 004_add_menu_sync_tables
Create Date: 2024-12-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '005_add_customer_system'
down_revision = '004_add_menu_sync_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create customer status enum
    customer_status_enum = sa.Enum(
        'active', 'inactive', 'suspended', 'deleted',
        name='customerstatus',
        create_type=False
    )
    customer_status_enum.create(op.get_bind(), checkfirst=True)
    
    # Create customer tier enum
    customer_tier_enum = sa.Enum(
        'bronze', 'silver', 'gold', 'platinum', 'vip',
        name='customertier',
        create_type=False
    )
    customer_tier_enum.create(op.get_bind(), checkfirst=True)
    
    # Create customers table
    op.create_table(
        'customers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=True),
        sa.Column('phone_verified', sa.Boolean(), nullable=True),
        sa.Column('email_verified', sa.Boolean(), nullable=True),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('login_count', sa.Integer(), nullable=True),
        sa.Column('date_of_birth', sa.DateTime(), nullable=True),
        sa.Column('gender', sa.String(length=20), nullable=True),
        sa.Column('profile_image_url', sa.String(length=500), nullable=True),
        sa.Column('status', customer_status_enum, nullable=False),
        sa.Column('tier', customer_tier_enum, nullable=False),
        sa.Column('tier_updated_at', sa.DateTime(), nullable=True),
        sa.Column('default_address_id', sa.Integer(), nullable=True),
        sa.Column('preferred_location_id', sa.Integer(), nullable=True),
        sa.Column('dietary_preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('allergens', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('favorite_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('communication_preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('marketing_opt_in', sa.Boolean(), nullable=True),
        sa.Column('loyalty_points', sa.Integer(), nullable=True),
        sa.Column('lifetime_points', sa.Integer(), nullable=True),
        sa.Column('points_expiry_date', sa.DateTime(), nullable=True),
        sa.Column('referral_code', sa.String(length=20), nullable=True),
        sa.Column('referred_by_customer_id', sa.Integer(), nullable=True),
        sa.Column('acquisition_source', sa.String(length=100), nullable=True),
        sa.Column('acquisition_date', sa.DateTime(), nullable=True),
        sa.Column('first_order_date', sa.DateTime(), nullable=True),
        sa.Column('last_order_date', sa.DateTime(), nullable=True),
        sa.Column('total_orders', sa.Integer(), nullable=True),
        sa.Column('total_spent', sa.Float(), nullable=True),
        sa.Column('average_order_value', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('custom_fields', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('external_id', sa.String(length=100), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['referred_by_customer_id'], ['customers.id'], ),
    )
    
    # Create indexes for customers table
    op.create_index('ix_customers_email', 'customers', ['email'], unique=True)
    op.create_index('ix_customers_phone', 'customers', ['phone'])
    op.create_index('ix_customers_status', 'customers', ['status'])
    op.create_index('ix_customers_tier', 'customers', ['tier'])
    op.create_index('ix_customers_external_id', 'customers', ['external_id'])
    op.create_index('ix_customers_name', 'customers', ['first_name', 'last_name'])
    op.create_index('ix_customers_tier_status', 'customers', ['tier', 'status'])
    op.create_index('ix_customers_location', 'customers', ['preferred_location_id'])
    op.create_index('ix_customers_acquisition', 'customers', ['acquisition_source', 'acquisition_date'])
    op.create_index('ix_customers_referral_code', 'customers', ['referral_code'], unique=True)
    
    # Create customer_addresses table
    op.create_table(
        'customer_addresses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=True),
        sa.Column('address_line1', sa.String(length=255), nullable=False),
        sa.Column('address_line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('state', sa.String(length=100), nullable=True),
        sa.Column('postal_code', sa.String(length=20), nullable=False),
        sa.Column('country', sa.String(length=2), nullable=False),
        sa.Column('delivery_instructions', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('is_billing', sa.Boolean(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    )
    
    # Create indexes for customer_addresses
    op.create_index('ix_customer_addresses_customer_id', 'customer_addresses', ['customer_id'])
    
    # Create customer_payment_methods table
    op.create_table(
        'customer_payment_methods',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('card_token', sa.String(length=255), nullable=True),
        sa.Column('card_last4', sa.String(length=4), nullable=True),
        sa.Column('card_brand', sa.String(length=50), nullable=True),
        sa.Column('card_exp_month', sa.Integer(), nullable=True),
        sa.Column('card_exp_year', sa.Integer(), nullable=True),
        sa.Column('wallet_id', sa.String(length=255), nullable=True),
        sa.Column('billing_address_id', sa.Integer(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['billing_address_id'], ['customer_addresses.id'], ),
    )
    
    # Create indexes for customer_payment_methods
    op.create_index('ix_customer_payment_methods_customer_id', 'customer_payment_methods', ['customer_id'])
    
    # Create customer_notifications table
    op.create_table(
        'customer_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    )
    
    # Create indexes for customer_notifications
    op.create_index('ix_customer_notifications_customer_id', 'customer_notifications', ['customer_id'])
    op.create_index('ix_customer_notifications_status', 'customer_notifications', ['customer_id', 'status'])
    op.create_index('ix_customer_notifications_type', 'customer_notifications', ['type', 'created_at'])
    
    # Create customer_segments table
    op.create_table(
        'customer_segments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('criteria', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('is_dynamic', sa.Boolean(), nullable=True),
        sa.Column('member_count', sa.Integer(), nullable=True),
        sa.Column('last_updated', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    
    # Create indexes for customer_segments
    op.create_index('ix_customer_segments_name', 'customer_segments', ['name'], unique=True)
    
    # Create customer_segment_members association table
    op.create_table(
        'customer_segment_members',
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('segment_id', sa.Integer(), nullable=False),
        sa.Column('added_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('customer_id', 'segment_id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.ForeignKeyConstraint(['segment_id'], ['customer_segments.id'], ),
    )
    
    # Create customer_rewards table
    op.create_table(
        'customer_rewards',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('points_cost', sa.Integer(), nullable=True),
        sa.Column('discount_amount', sa.Float(), nullable=True),
        sa.Column('discount_percentage', sa.Float(), nullable=True),
        sa.Column('item_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=True),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(), nullable=True),
        sa.Column('min_order_amount', sa.Float(), nullable=True),
        sa.Column('applicable_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('applicable_items', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    )
    
    # Create indexes for customer_rewards
    op.create_index('ix_customer_rewards_customer_id', 'customer_rewards', ['customer_id'])
    op.create_index('ix_customer_rewards_status', 'customer_rewards', ['customer_id', 'status'])
    op.create_index('ix_customer_rewards_validity', 'customer_rewards', ['valid_from', 'valid_until'])
    op.create_index('ix_customer_rewards_code', 'customer_rewards', ['code'], unique=True)
    
    # Create customer_preferences table
    op.create_table(
        'customer_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('preference_key', sa.String(length=100), nullable=False),
        sa.Column('preference_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
        sa.UniqueConstraint('customer_id', 'category', 'preference_key'),
    )
    
    # Create indexes for customer_preferences
    op.create_index('ix_customer_preferences_customer_id', 'customer_preferences', ['customer_id'])
    op.create_index('ix_customer_preferences_category', 'customer_preferences', ['category', 'preference_key'])
    
    # Update default address foreign key constraint
    op.create_foreign_key(
        'fk_customers_default_address_id',
        'customers', 'customer_addresses',
        ['default_address_id'], ['id']
    )
    
    # Add customer_id column to orders table
    op.add_column('orders', sa.Column('customer_id', sa.Integer(), nullable=True))
    op.create_index('ix_orders_customer_id', 'orders', ['customer_id'])
    op.create_foreign_key(
        'fk_orders_customer_id',
        'orders', 'customers',
        ['customer_id'], ['id']
    )
    
    # Set default values for new columns
    op.execute("UPDATE customers SET phone_verified = false WHERE phone_verified IS NULL")
    op.execute("UPDATE customers SET email_verified = false WHERE email_verified IS NULL")
    op.execute("UPDATE customers SET login_count = 0 WHERE login_count IS NULL")
    op.execute("UPDATE customers SET status = 'active' WHERE status IS NULL")
    op.execute("UPDATE customers SET tier = 'bronze' WHERE tier IS NULL")
    op.execute("UPDATE customers SET marketing_opt_in = true WHERE marketing_opt_in IS NULL")
    op.execute("UPDATE customers SET loyalty_points = 0 WHERE loyalty_points IS NULL")
    op.execute("UPDATE customers SET lifetime_points = 0 WHERE lifetime_points IS NULL")
    op.execute("UPDATE customers SET total_orders = 0 WHERE total_orders IS NULL")
    op.execute("UPDATE customers SET total_spent = 0.0 WHERE total_spent IS NULL")
    op.execute("UPDATE customers SET average_order_value = 0.0 WHERE average_order_value IS NULL")
    op.execute("UPDATE customers SET acquisition_date = NOW() WHERE acquisition_date IS NULL")
    
    op.execute("UPDATE customer_addresses SET is_default = false WHERE is_default IS NULL")
    op.execute("UPDATE customer_addresses SET is_billing = false WHERE is_billing IS NULL")
    op.execute("UPDATE customer_addresses SET is_verified = false WHERE is_verified IS NULL")
    op.execute("UPDATE customer_addresses SET country = 'US' WHERE country IS NULL")
    
    op.execute("UPDATE customer_payment_methods SET is_default = false WHERE is_default IS NULL")
    op.execute("UPDATE customer_payment_methods SET is_active = true WHERE is_active IS NULL")
    
    op.execute("UPDATE customer_notifications SET status = 'pending' WHERE status IS NULL")
    
    op.execute("UPDATE customer_segments SET is_active = true WHERE is_active IS NULL")
    op.execute("UPDATE customer_segments SET is_dynamic = false WHERE is_dynamic IS NULL")
    op.execute("UPDATE customer_segments SET member_count = 0 WHERE member_count IS NULL")
    op.execute("UPDATE customer_segments SET last_updated = NOW() WHERE last_updated IS NULL")
    
    op.execute("UPDATE customer_rewards SET status = 'available' WHERE status IS NULL")
    op.execute("UPDATE customer_rewards SET valid_from = NOW() WHERE valid_from IS NULL")
    
    op.execute("UPDATE customer_segment_members SET added_at = NOW() WHERE added_at IS NULL")


def downgrade():
    # Drop foreign key and index for orders.customer_id
    op.drop_constraint('fk_orders_customer_id', 'orders', type_='foreignkey')
    op.drop_index('ix_orders_customer_id', 'orders')
    op.drop_column('orders', 'customer_id')
    
    # Drop foreign key constraint for default_address_id
    op.drop_constraint('fk_customers_default_address_id', 'customers', type_='foreignkey')
    
    # Drop all customer tables in reverse order
    op.drop_table('customer_preferences')
    op.drop_table('customer_rewards')
    op.drop_table('customer_segment_members')
    op.drop_table('customer_segments')
    op.drop_table('customer_notifications')
    op.drop_table('customer_payment_methods')
    op.drop_table('customer_addresses')
    op.drop_table('customers')
    
    # Drop enums
    sa.Enum(name='customertier').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='customerstatus').drop(op.get_bind(), checkfirst=True)