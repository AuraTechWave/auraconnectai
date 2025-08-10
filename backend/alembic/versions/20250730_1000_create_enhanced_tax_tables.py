"""Create enhanced tax tables for AUR-304

Revision ID: 20250730_1000
Revises: previous_revision
Create Date: 2025-07-30 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250730_1000'
down_revision = '20250729_1900_add_feedback_and_reviews_tables'
branch_labels = None
depends_on = None


def upgrade():
    # Create tax_jurisdictions table
    op.create_table(
        'tax_jurisdictions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('jurisdiction_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('jurisdiction_type', sa.String(length=50), nullable=False),
        sa.Column('parent_jurisdiction_id', sa.Integer(), nullable=True),
        sa.Column('country_code', sa.String(length=2), nullable=False),
        sa.Column('state_code', sa.String(length=10), nullable=True),
        sa.Column('county_name', sa.String(length=100), nullable=True),
        sa.Column('city_name', sa.String(length=100), nullable=True),
        sa.Column('zip_codes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('filing_frequency', sa.String(length=50), nullable=True),
        sa.Column('filing_due_day', sa.Integer(), nullable=True),
        sa.Column('registration_number', sa.String(length=100), nullable=True),
        sa.Column('tax_id', sa.String(length=100), nullable=True),
        sa.Column('tax_authority_name', sa.String(length=200), nullable=True),
        sa.Column('tax_authority_website', sa.String(length=500), nullable=True),
        sa.Column('tax_authority_phone', sa.String(length=50), nullable=True),
        sa.Column('tax_authority_email', sa.String(length=200), nullable=True),
        sa.Column('tax_authority_address', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['parent_jurisdiction_id'], ['tax_jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('jurisdiction_id'),
        sa.UniqueConstraint('code', 'jurisdiction_type', 'tenant_id', name='uq_jurisdiction_code_type_tenant')
    )
    op.create_index('idx_jurisdiction_location', 'tax_jurisdictions', ['country_code', 'state_code'], unique=False)
    op.create_index('idx_jurisdiction_type_active', 'tax_jurisdictions', ['jurisdiction_type', 'is_active'], unique=False)

    # Create tax_rates table
    op.create_table(
        'tax_rates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jurisdiction_id', sa.Integer(), nullable=False),
        sa.Column('tax_type', sa.String(length=50), nullable=False),
        sa.Column('tax_subtype', sa.String(length=50), nullable=True),
        sa.Column('tax_category', sa.String(length=100), nullable=True),
        sa.Column('rate_percent', sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column('flat_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('min_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('max_amount', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('bracket_name', sa.String(length=100), nullable=True),
        sa.Column('applies_to', sa.String(length=100), nullable=True),
        sa.Column('exemption_categories', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('compound_on', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ordering', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('calculation_method', sa.String(length=50), nullable=False, server_default='percentage'),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('flat_amount >= 0', name='check_flat_amount_non_negative'),
        sa.CheckConstraint('rate_percent >= 0', name='check_rate_non_negative'),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['tax_jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rate_id'),
        sa.UniqueConstraint('jurisdiction_id', 'tax_type', 'tax_subtype', 'tax_category', 'effective_date', 'tenant_id', 
                          name='uq_tax_rate_jurisdiction_type_date')
    )
    op.create_index('idx_tax_rate_jurisdiction_type', 'tax_rates', ['jurisdiction_id', 'tax_type'], unique=False)
    op.create_index('idx_tax_rate_type_active', 'tax_rates', ['tax_type', 'is_active'], unique=False)

    # Create tax_rule_configurations table
    op.create_table(
        'tax_rule_configurations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('rule_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rule_name', sa.String(length=200), nullable=False),
        sa.Column('rule_code', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('jurisdiction_id', sa.Integer(), nullable=False),
        sa.Column('tax_type', sa.String(length=50), nullable=False),
        sa.Column('rule_type', sa.String(length=100), nullable=False),
        sa.Column('conditions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('requires_documentation', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('documentation_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['tax_jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('rule_code'),
        sa.UniqueConstraint('rule_id')
    )
    op.create_index('idx_tax_rule_jurisdiction', 'tax_rule_configurations', ['jurisdiction_id', 'tax_type'], unique=False)
    op.create_index('idx_tax_rule_type_active', 'tax_rule_configurations', ['rule_type', 'is_active'], unique=False)

    # Create tax_exemption_certificates table
    op.create_table(
        'tax_exemption_certificates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('certificate_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('customer_name', sa.String(length=200), nullable=False),
        sa.Column('customer_tax_id', sa.String(length=100), nullable=True),
        sa.Column('certificate_number', sa.String(length=100), nullable=False),
        sa.Column('exemption_type', sa.String(length=100), nullable=False),
        sa.Column('exemption_reason', sa.Text(), nullable=True),
        sa.Column('jurisdiction_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('tax_types', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('issue_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('verified_date', sa.Date(), nullable=True),
        sa.Column('verified_by', sa.String(length=100), nullable=True),
        sa.Column('document_url', sa.String(length=500), nullable=True),
        sa.Column('document_hash', sa.String(length=200), nullable=True),
        sa.Column('last_used_date', sa.Date(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('certificate_id'),
        sa.UniqueConstraint('certificate_number', 'tenant_id', name='uq_certificate_number_tenant')
    )
    op.create_index('idx_exemption_customer', 'tax_exemption_certificates', ['customer_id', 'is_active'], unique=False)
    op.create_index('idx_exemption_expiry', 'tax_exemption_certificates', ['expiry_date', 'is_active'], unique=False)

    # Create tax_nexus table
    op.create_table(
        'tax_nexus',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nexus_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jurisdiction_id', sa.Integer(), nullable=False),
        sa.Column('nexus_type', sa.String(length=50), nullable=False),
        sa.Column('establishment_date', sa.Date(), nullable=False),
        sa.Column('registration_date', sa.Date(), nullable=True),
        sa.Column('registration_number', sa.String(length=100), nullable=True),
        sa.Column('sales_threshold', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('transaction_threshold', sa.Integer(), nullable=True),
        sa.Column('threshold_period', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('requires_filing', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_filing_date', sa.Date(), nullable=True),
        sa.Column('next_filing_date', sa.Date(), nullable=True),
        sa.Column('filing_frequency', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['tax_jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('nexus_id'),
        sa.UniqueConstraint('jurisdiction_id', 'nexus_type', 'tenant_id', name='uq_nexus_jurisdiction_type_tenant')
    )
    op.create_index('idx_nexus_active', 'tax_nexus', ['is_active', 'requires_filing'], unique=False)

    # Create tax_filings table
    op.create_table(
        'tax_filings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filing_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filing_number', sa.String(length=100), nullable=True),
        sa.Column('internal_reference', sa.String(length=100), nullable=False),
        sa.Column('jurisdiction_id', sa.Integer(), nullable=False),
        sa.Column('filing_type', sa.Enum('sales_tax', 'income_tax', 'payroll_tax', 'property_tax', 'excise_tax', 'franchise_tax', 'other', 
                                       name='filingtype'), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('draft', 'ready', 'submitted', 'accepted', 'rejected', 'amended', 'paid', 
                                   name='filingstatus'), nullable=False, server_default='draft'),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('filed_date', sa.DateTime(), nullable=True),
        sa.Column('gross_sales', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('taxable_sales', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('exempt_sales', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tax_collected', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tax_due', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('penalties', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('interest', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('total_due', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('payment_status', sa.String(length=50), nullable=True),
        sa.Column('payment_date', sa.Date(), nullable=True),
        sa.Column('payment_reference', sa.String(length=100), nullable=True),
        sa.Column('payment_method', sa.String(length=50), nullable=True),
        sa.Column('form_type', sa.String(length=50), nullable=True),
        sa.Column('confirmation_number', sa.String(length=100), nullable=True),
        sa.Column('prepared_by', sa.String(length=100), nullable=True),
        sa.Column('prepared_date', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.String(length=100), nullable=True),
        sa.Column('reviewed_date', sa.DateTime(), nullable=True),
        sa.Column('approved_by', sa.String(length=100), nullable=True),
        sa.Column('approved_date', sa.DateTime(), nullable=True),
        sa.Column('attachments', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_amended', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('amendment_reason', sa.Text(), nullable=True),
        sa.Column('original_filing_id', sa.Integer(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('period_end >= period_start', name='check_period_valid'),
        sa.CheckConstraint('tax_due >= 0', name='check_tax_due_non_negative'),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['tax_jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['original_filing_id'], ['tax_filings.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filing_id'),
        sa.UniqueConstraint('internal_reference', 'tenant_id', name='uq_filing_reference_tenant')
    )
    op.create_index('idx_filing_jurisdiction_period', 'tax_filings', ['jurisdiction_id', 'period_start', 'period_end'], unique=False)
    op.create_index('idx_filing_status_due', 'tax_filings', ['status', 'due_date'], unique=False)

    # Create tax_filing_line_items table
    op.create_table(
        'tax_filing_line_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filing_id', sa.Integer(), nullable=False),
        sa.Column('line_number', sa.String(length=20), nullable=False),
        sa.Column('description', sa.String(length=500), nullable=False),
        sa.Column('tax_category', sa.String(length=100), nullable=True),
        sa.Column('gross_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('deductions', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('exemptions', sa.Numeric(precision=12, scale=2), nullable=False, server_default='0'),
        sa.Column('taxable_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('tax_rate', sa.Numeric(precision=8, scale=5), nullable=False),
        sa.Column('tax_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('location_code', sa.String(length=50), nullable=True),
        sa.Column('product_category', sa.String(length=100), nullable=True),
        sa.Column('transaction_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('tax_amount >= 0', name='check_tax_amount_non_negative'),
        sa.CheckConstraint('taxable_amount >= 0', name='check_taxable_amount_non_negative'),
        sa.ForeignKeyConstraint(['filing_id'], ['tax_filings.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filing_id', 'line_number', name='uq_filing_line_number')
    )

    # Create tax_remittances table
    op.create_table(
        'tax_remittances',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('remittance_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('payment_date', sa.Date(), nullable=False),
        sa.Column('payment_method', sa.String(length=50), nullable=False),
        sa.Column('payment_reference', sa.String(length=100), nullable=False),
        sa.Column('payment_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('filing_references', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('bank_account_last4', sa.String(length=4), nullable=True),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('confirmation_code', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('processed_date', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('payment_amount > 0', name='check_payment_amount_positive'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('remittance_id'),
        sa.UniqueConstraint('payment_reference', 'tenant_id', name='uq_payment_reference_tenant')
    )
    op.create_index('idx_remittance_date_status', 'tax_remittances', ['payment_date', 'status'], unique=False)

    # Create tax_audit_logs table
    op.create_table(
        'tax_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_subtype', sa.String(length=100), nullable=True),
        sa.Column('event_timestamp', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=100), nullable=False),
        sa.Column('filing_id', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.String(length=100), nullable=False),
        sa.Column('user_name', sa.String(length=200), nullable=True),
        sa.Column('user_role', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('amount_before', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('amount_after', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tax_impact', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['filing_id'], ['tax_filings.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('audit_id')
    )
    op.create_index('idx_audit_entity', 'tax_audit_logs', ['entity_type', 'entity_id'], unique=False)
    op.create_index('idx_audit_event_type', 'tax_audit_logs', ['event_type', 'event_subtype'], unique=False)
    op.create_index('idx_audit_timestamp', 'tax_audit_logs', ['event_timestamp'], unique=False)
    op.create_index('idx_audit_user', 'tax_audit_logs', ['user_id', 'event_timestamp'], unique=False)

    # Create tax_report_templates table
    op.create_table(
        'tax_report_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('template_code', sa.String(length=100), nullable=False),
        sa.Column('template_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(length=100), nullable=False),
        sa.Column('filing_type', sa.Enum('sales_tax', 'income_tax', 'payroll_tax', 'property_tax', 'excise_tax', 'franchise_tax', 'other', 
                                       name='filingtype'), nullable=True),
        sa.Column('jurisdiction_id', sa.Integer(), nullable=True),
        sa.Column('template_format', sa.String(length=50), nullable=False),
        sa.Column('template_schema', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('template_layout', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('validation_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=False, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('expiry_date', sa.Date(), nullable=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['jurisdiction_id'], ['tax_jurisdictions.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id'),
        sa.UniqueConstraint('template_code', 'version', 'tenant_id', name='uq_template_code_version_tenant')
    )
    op.create_index('idx_template_type_active', 'tax_report_templates', ['report_type', 'is_active'], unique=False)


def downgrade():
    # Drop indexes
    op.drop_index('idx_template_type_active', table_name='tax_report_templates')
    op.drop_index('idx_audit_user', table_name='tax_audit_logs')
    op.drop_index('idx_audit_timestamp', table_name='tax_audit_logs')
    op.drop_index('idx_audit_event_type', table_name='tax_audit_logs')
    op.drop_index('idx_audit_entity', table_name='tax_audit_logs')
    op.drop_index('idx_remittance_date_status', table_name='tax_remittances')
    op.drop_index('idx_filing_status_due', table_name='tax_filings')
    op.drop_index('idx_filing_jurisdiction_period', table_name='tax_filings')
    op.drop_index('idx_nexus_active', table_name='tax_nexus')
    op.drop_index('idx_exemption_expiry', table_name='tax_exemption_certificates')
    op.drop_index('idx_exemption_customer', table_name='tax_exemption_certificates')
    op.drop_index('idx_tax_rule_type_active', table_name='tax_rule_configurations')
    op.drop_index('idx_tax_rule_jurisdiction', table_name='tax_rule_configurations')
    op.drop_index('idx_tax_rate_type_active', table_name='tax_rates')
    op.drop_index('idx_tax_rate_jurisdiction_type', table_name='tax_rates')
    op.drop_index('idx_jurisdiction_type_active', table_name='tax_jurisdictions')
    op.drop_index('idx_jurisdiction_location', table_name='tax_jurisdictions')
    
    # Drop tables
    op.drop_table('tax_report_templates')
    op.drop_table('tax_audit_logs')
    op.drop_table('tax_remittances')
    op.drop_table('tax_filing_line_items')
    op.drop_table('tax_filings')
    op.drop_table('tax_nexus')
    op.drop_table('tax_exemption_certificates')
    op.drop_table('tax_rule_configurations')
    op.drop_table('tax_rates')
    op.drop_table('tax_jurisdictions')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS filingtype')
    op.execute('DROP TYPE IF EXISTS filingstatus')