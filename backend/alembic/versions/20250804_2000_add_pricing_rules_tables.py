"""Add pricing rules tables

Revision ID: add_pricing_rules_tables
Revises: add_refund_processing_tables
Create Date: 2025-08-04 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_pricing_rules_tables'
down_revision = 'add_refund_processing_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create rule type enum
    op.execute("""
        CREATE TYPE rule_type AS ENUM (
            'percentage_discount', 'fixed_discount', 'bundle_discount',
            'bogo', 'happy_hour', 'loyalty_discount', 'quantity_discount',
            'category_discount', 'time_based', 'custom'
        );
    """)
    
    # Create rule status enum
    op.execute("""
        CREATE TYPE rule_status AS ENUM (
            'active', 'inactive', 'scheduled', 'expired', 'testing'
        );
    """)
    
    # Create conflict resolution enum
    op.execute("""
        CREATE TYPE conflict_resolution AS ENUM (
            'highest_discount', 'first_match', 'combine_additive',
            'combine_multiplicative', 'priority_based'
        );
    """)
    
    # Create pricing_rules table
    op.create_table(
        'pricing_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.String(50), nullable=False),
        
        # Basic info
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', postgresql.ENUM('percentage_discount', 'fixed_discount', 'bundle_discount',
                                               'bogo', 'happy_hour', 'loyalty_discount', 'quantity_discount',
                                               'category_discount', 'time_based', 'custom',
                                               name='rule_type', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('active', 'inactive', 'scheduled', 'expired', 'testing',
                                           name='rule_status', create_type=False), 
                 nullable=False, server_default='active'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
        
        # Restaurant association
        sa.Column('restaurant_id', sa.Integer(), nullable=False),
        
        # Rule configuration
        sa.Column('discount_value', sa.Numeric(10, 2), nullable=True),
        sa.Column('max_discount_amount', sa.Numeric(10, 2), nullable=True),
        sa.Column('min_order_amount', sa.Numeric(10, 2), nullable=True),
        
        # Conditions (JSON)
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        
        # Validity period
        sa.Column('valid_from', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        
        # Usage limits
        sa.Column('max_uses_total', sa.Integer(), nullable=True),
        sa.Column('max_uses_per_customer', sa.Integer(), nullable=True),
        sa.Column('current_uses', sa.Integer(), nullable=False, server_default='0'),
        
        # Stacking rules
        sa.Column('stackable', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('excluded_rule_ids', postgresql.JSONB(astext_type=sa.Text()), 
                 nullable=False, server_default='[]'),
        sa.Column('conflict_resolution', 
                 postgresql.ENUM('highest_discount', 'first_match', 'combine_additive',
                               'combine_multiplicative', 'priority_based',
                               name='conflict_resolution', create_type=False),
                 nullable=False, server_default='highest_discount'),
        
        # Tracking
        sa.Column('requires_code', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('promo_code', sa.String(50), nullable=True),
        
        # Metadata
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('rule_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_id'),
        sa.ForeignKeyConstraint(['restaurant_id'], ['restaurants.id']),
        sa.CheckConstraint('priority >= 1 AND priority <= 5', name='check_priority_range'),
    )
    
    # Create indexes
    op.create_index('idx_rule_restaurant_status', 'pricing_rules', ['restaurant_id', 'status'])
    op.create_index('idx_rule_validity', 'pricing_rules', ['valid_from', 'valid_until'])
    op.create_index('idx_rule_type_status', 'pricing_rules', ['rule_type', 'status'])
    op.create_index('idx_rule_promo_code', 'pricing_rules', ['promo_code'])
    
    # Create pricing_rule_applications table
    op.create_table(
        'pricing_rule_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        
        # References
        sa.Column('rule_id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('order_item_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        
        # Application details
        sa.Column('discount_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('original_amount', sa.Numeric(10, 2), nullable=False),
        sa.Column('final_amount', sa.Numeric(10, 2), nullable=False),
        
        # Tracking
        sa.Column('applied_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('applied_by', sa.String(50), nullable=True),
        
        # Debug info
        sa.Column('conditions_met', postgresql.JSONB(astext_type=sa.Text()), 
                 nullable=False, server_default='{}'),
        sa.Column('application_metadata', postgresql.JSONB(astext_type=sa.Text()), 
                 nullable=False, server_default='{}'),
        
        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['rule_id'], ['pricing_rules.id']),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id']),
        sa.ForeignKeyConstraint(['order_item_id'], ['order_items.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customers.id']),
    )
    
    # Create indexes
    op.create_index('idx_application_order', 'pricing_rule_applications', ['order_id'])
    op.create_index('idx_application_rule', 'pricing_rule_applications', ['rule_id'])
    op.create_index('idx_application_customer', 'pricing_rule_applications', ['customer_id'])
    op.create_index('idx_application_date', 'pricing_rule_applications', ['applied_at'])
    
    # Create pricing_rule_metrics table
    op.create_table(
        'pricing_rule_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_id', sa.Integer(), nullable=False),
        
        # Aggregated metrics
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('applications_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_discount_amount', sa.Numeric(12, 2), nullable=False, server_default='0'),
        sa.Column('unique_customers', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('conversion_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('average_order_value', sa.Numeric(10, 2), nullable=True),
        
        # Performance metrics
        sa.Column('conflicts_skipped', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('stacking_count', sa.Integer(), nullable=False, server_default='0'),
        
        # Metadata
        sa.Column('metrics_metadata', postgresql.JSONB(astext_type=sa.Text()), 
                 nullable=False, server_default='{}'),
        
        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_id', 'date', name='uq_rule_metrics_date'),
        sa.ForeignKeyConstraint(['rule_id'], ['pricing_rules.id']),
    )
    
    # Create index
    op.create_index('idx_metrics_rule_date', 'pricing_rule_metrics', ['rule_id', 'date'])
    
    # Add triggers for updated_at
    for table in ['pricing_rules', 'pricing_rule_applications']:
        op.execute(f"""
            CREATE TRIGGER update_{table}_updated_at BEFORE UPDATE ON {table}
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
    
    # Add default conflict resolution to restaurants table if not exists
    try:
        op.add_column('restaurants', 
                     sa.Column('default_conflict_resolution',
                              postgresql.ENUM('highest_discount', 'first_match', 'combine_additive',
                                            'combine_multiplicative', 'priority_based',
                                            name='conflict_resolution', create_type=False),
                              nullable=True,
                              server_default='highest_discount'))
    except:
        # Column might already exist
        pass


def downgrade():
    # Drop triggers
    for table in ['pricing_rules', 'pricing_rule_applications']:
        op.execute(f"DROP TRIGGER IF EXISTS update_{table}_updated_at ON {table};")
    
    # Drop tables
    op.drop_table('pricing_rule_metrics')
    op.drop_table('pricing_rule_applications')
    op.drop_table('pricing_rules')
    
    # Drop column from restaurants if exists
    try:
        op.drop_column('restaurants', 'default_conflict_resolution')
    except:
        pass
    
    # Drop enums
    op.execute("DROP TYPE IF EXISTS conflict_resolution;")
    op.execute("DROP TYPE IF EXISTS rule_status;")
    op.execute("DROP TYPE IF EXISTS rule_type;")