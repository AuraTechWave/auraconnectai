"""Create payroll configuration tables for production-ready business logic

Revision ID: 20250726_1200_0011
Revises: 20250125_2045_0010
Create Date: 2025-07-26 12:00:00.000000

This migration creates configurable business logic tables to replace hardcoded values:
1. payroll_configurations - General configuration settings
2. staff_pay_policies - Staff-specific pay policies  
3. overtime_rules - Jurisdiction-specific overtime rules
4. tax_approximation_rules - Configurable tax breakdown percentages
5. role_based_pay_rates - Role-based default pay rates
6. payroll_job_tracking - Persistent job status tracking

Addresses business logic concerns from code review about:
- Fixed benefit deduction factors (0.46)
- Static policy data from get_staff_pay_policy
- Hardcoded overtime rules and tax approximations
- In-memory job tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250726_1200_0011'
down_revision = '20250125_2045_0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create payroll configuration tables."""
    
    # Create PayrollConfigurationType enum
    payroll_config_type_enum = postgresql.ENUM(
        'benefit_proration', 'overtime_rules', 'tax_approximation', 
        'role_rates', 'jurisdiction_rules',
        name='payrollconfigurationtype'
    )
    payroll_config_type_enum.create(op.get_bind())
    
    # Create payroll_configurations table
    op.create_table(
        'payroll_configurations',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('config_type', payroll_config_type_enum, nullable=False, index=True),
        sa.Column('config_key', sa.String(100), nullable=False, index=True),
        sa.Column('config_value', sa.JSON, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('location', sa.String(100), nullable=True, index=True),
        sa.Column('tenant_id', sa.Integer, nullable=True, index=True),
        sa.Column('effective_date', sa.DateTime, nullable=False),
        sa.Column('expiry_date', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        comment='Configurable payroll business logic settings'
    )
    
    # Create staff_pay_policies table
    op.create_table(
        'staff_pay_policies',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('staff_id', sa.Integer, sa.ForeignKey('staff_members.id'), nullable=False, index=True),
        sa.Column('location', sa.String(100), nullable=False, index=True),
        
        # Pay rates
        sa.Column('base_hourly_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('overtime_multiplier', sa.Numeric(5, 4), default=1.5, nullable=False),
        sa.Column('double_time_multiplier', sa.Numeric(5, 4), default=2.0, nullable=False),
        
        # Overtime rules - configurable thresholds
        sa.Column('daily_overtime_threshold', sa.Numeric(6, 2), nullable=True),
        sa.Column('weekly_overtime_threshold', sa.Numeric(6, 2), default=40.0, nullable=False),
        
        # Benefit deductions (monthly amounts)
        sa.Column('health_insurance_monthly', sa.Numeric(8, 2), default=0.00, nullable=False),
        sa.Column('dental_insurance_monthly', sa.Numeric(8, 2), default=0.00, nullable=False),
        sa.Column('retirement_contribution_monthly', sa.Numeric(8, 2), default=0.00, nullable=False),
        sa.Column('parking_fee_monthly', sa.Numeric(8, 2), default=0.00, nullable=False),
        
        # Proration settings - configurable factors
        sa.Column('benefit_proration_factor', sa.Numeric(5, 4), nullable=False),
        sa.Column('pay_frequency_factor', sa.Numeric(5, 4), nullable=False),
        
        # Metadata
        sa.Column('effective_date', sa.DateTime, nullable=False),
        sa.Column('expiry_date', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('tenant_id', sa.Integer, nullable=True, index=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        comment='Staff-specific pay policies and configurations'
    )
    
    # Create overtime_rules table
    op.create_table(
        'overtime_rules',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('jurisdiction', sa.String(100), nullable=False, index=True),
        
        # Daily overtime rules
        sa.Column('daily_threshold_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('daily_overtime_multiplier', sa.Numeric(5, 4), nullable=True),
        sa.Column('daily_double_time_threshold', sa.Numeric(6, 2), nullable=True),
        sa.Column('daily_double_time_multiplier', sa.Numeric(5, 4), nullable=True),
        
        # Weekly overtime rules
        sa.Column('weekly_threshold_hours', sa.Numeric(6, 2), nullable=True),
        sa.Column('weekly_overtime_multiplier', sa.Numeric(5, 4), nullable=True),
        
        # Consecutive day rules (e.g., 7th consecutive day)
        sa.Column('consecutive_days_threshold', sa.Integer, nullable=True),
        sa.Column('consecutive_days_multiplier', sa.Numeric(5, 4), nullable=True),
        
        # Holiday and special day rules
        sa.Column('holiday_multiplier', sa.Numeric(5, 4), nullable=True),
        sa.Column('sunday_multiplier', sa.Numeric(5, 4), nullable=True),
        
        # Rule precedence (higher number = higher priority)
        sa.Column('precedence', sa.Integer, default=0, nullable=False),
        
        # Metadata
        sa.Column('effective_date', sa.DateTime, nullable=False),
        sa.Column('expiry_date', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('tenant_id', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        comment='Configurable overtime rules by jurisdiction'
    )
    
    # Create tax_approximation_rules table
    op.create_table(
        'tax_approximation_rules',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('jurisdiction', sa.String(100), nullable=False, index=True),
        
        # Approximation percentages for tax breakdown
        sa.Column('federal_tax_percentage', sa.Numeric(5, 4), nullable=False),
        sa.Column('state_tax_percentage', sa.Numeric(5, 4), nullable=False),
        sa.Column('local_tax_percentage', sa.Numeric(5, 4), default=0.0, nullable=False),
        sa.Column('social_security_percentage', sa.Numeric(5, 4), nullable=False),
        sa.Column('medicare_percentage', sa.Numeric(5, 4), nullable=False),
        sa.Column('unemployment_percentage', sa.Numeric(5, 4), default=0.0, nullable=False),
        
        # Total should equal 1.0 for validation
        sa.Column('total_percentage', sa.Numeric(5, 4), nullable=False),
        
        # Metadata
        sa.Column('effective_date', sa.DateTime, nullable=False),
        sa.Column('expiry_date', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('tenant_id', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        comment='Tax breakdown approximation rules when exact values unavailable'
    )
    
    # Create role_based_pay_rates table
    op.create_table(
        'role_based_pay_rates',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('role_name', sa.String(50), nullable=False, index=True),
        sa.Column('location', sa.String(100), nullable=False, index=True),
        
        # Pay rate information
        sa.Column('default_hourly_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('minimum_hourly_rate', sa.Numeric(10, 4), nullable=False),
        sa.Column('maximum_hourly_rate', sa.Numeric(10, 4), nullable=True),
        
        # Experience-based adjustments
        sa.Column('entry_level_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('experienced_rate', sa.Numeric(10, 4), nullable=True),
        sa.Column('senior_rate', sa.Numeric(10, 4), nullable=True),
        
        # Overtime settings
        sa.Column('overtime_eligible', sa.Boolean, default=True, nullable=False),
        sa.Column('overtime_multiplier', sa.Numeric(5, 4), default=1.5, nullable=False),
        
        # Metadata
        sa.Column('effective_date', sa.DateTime, nullable=False),
        sa.Column('expiry_date', sa.DateTime, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('tenant_id', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        comment='Role-based default pay rates by location'
    )
    
    # Create payroll_job_tracking table
    op.create_table(
        'payroll_job_tracking',
        sa.Column('id', sa.Integer, primary_key=True, index=True),
        sa.Column('job_id', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('job_type', sa.String(50), nullable=False),  # 'batch_payroll', 'export', etc.
        
        # Job parameters
        sa.Column('staff_ids', sa.JSON, nullable=True),
        sa.Column('pay_period_start', sa.DateTime, nullable=True),
        sa.Column('pay_period_end', sa.DateTime, nullable=True),
        sa.Column('tenant_id', sa.Integer, nullable=True),
        
        # Status tracking
        sa.Column('status', sa.String(50), default='pending', nullable=False, index=True),
        sa.Column('total_items', sa.Integer, default=0, nullable=False),
        sa.Column('completed_items', sa.Integer, default=0, nullable=False),
        sa.Column('failed_items', sa.Integer, default=0, nullable=False),
        
        # Progress and timing
        sa.Column('progress_percentage', sa.Integer, default=0, nullable=False),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('estimated_completion', sa.DateTime, nullable=True),
        
        # Results and errors
        sa.Column('result_data', sa.JSON, nullable=True),
        sa.Column('error_details', sa.JSON, nullable=True),
        
        # Metadata
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('tenant_id_filter', sa.Integer, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        comment='Persistent tracking for batch payroll operations'
    )
    
    # Add indexes for performance
    op.create_index('ix_payroll_configurations_type_location', 'payroll_configurations', ['config_type', 'location'])
    op.create_index('ix_staff_pay_policies_staff_active', 'staff_pay_policies', ['staff_id', 'is_active'])
    op.create_index('ix_overtime_rules_jurisdiction_active', 'overtime_rules', ['jurisdiction', 'is_active'])
    op.create_index('ix_tax_approximation_rules_jurisdiction_active', 'tax_approximation_rules', ['jurisdiction', 'is_active'])
    op.create_index('ix_role_based_pay_rates_role_location', 'role_based_pay_rates', ['role_name', 'location'])
    op.create_index('ix_payroll_job_tracking_status_created', 'payroll_job_tracking', ['status', 'created_at'])
    
    # Add check constraints for data validation
    op.create_check_constraint(
        'ck_staff_pay_policies_rates_positive',
        'staff_pay_policies',
        'base_hourly_rate > 0 AND overtime_multiplier >= 1.0 AND double_time_multiplier >= 1.0'
    )
    
    op.create_check_constraint(
        'ck_staff_pay_policies_thresholds_positive',
        'staff_pay_policies',
        'weekly_overtime_threshold > 0 AND (daily_overtime_threshold IS NULL OR daily_overtime_threshold > 0)'
    )
    
    op.create_check_constraint(
        'ck_overtime_rules_multipliers_valid',
        'overtime_rules',
        '(daily_overtime_multiplier IS NULL OR daily_overtime_multiplier >= 1.0) AND (weekly_overtime_multiplier IS NULL OR weekly_overtime_multiplier >= 1.0)'
    )
    
    op.create_check_constraint(
        'ck_tax_approximation_rules_percentages_valid',
        'tax_approximation_rules',
        'federal_tax_percentage >= 0 AND federal_tax_percentage <= 1 AND state_tax_percentage >= 0 AND state_tax_percentage <= 1'
    )
    
    op.create_check_constraint(
        'ck_role_based_pay_rates_rates_positive',
        'role_based_pay_rates',
        'default_hourly_rate > 0 AND minimum_hourly_rate > 0 AND overtime_multiplier >= 1.0'
    )
    
    op.create_check_constraint(
        'ck_payroll_job_tracking_progress_valid',
        'payroll_job_tracking',
        'progress_percentage >= 0 AND progress_percentage <= 100'
    )


def downgrade() -> None:
    """Remove payroll configuration tables."""
    
    # Drop check constraints
    op.drop_constraint('ck_payroll_job_tracking_progress_valid', 'payroll_job_tracking')
    op.drop_constraint('ck_role_based_pay_rates_rates_positive', 'role_based_pay_rates')
    op.drop_constraint('ck_tax_approximation_rules_percentages_valid', 'tax_approximation_rules')
    op.drop_constraint('ck_overtime_rules_multipliers_valid', 'overtime_rules')
    op.drop_constraint('ck_staff_pay_policies_thresholds_positive', 'staff_pay_policies')
    op.drop_constraint('ck_staff_pay_policies_rates_positive', 'staff_pay_policies')
    
    # Drop indexes
    op.drop_index('ix_payroll_job_tracking_status_created', 'payroll_job_tracking')
    op.drop_index('ix_role_based_pay_rates_role_location', 'role_based_pay_rates')
    op.drop_index('ix_tax_approximation_rules_jurisdiction_active', 'tax_approximation_rules')
    op.drop_index('ix_overtime_rules_jurisdiction_active', 'overtime_rules')
    op.drop_index('ix_staff_pay_policies_staff_active', 'staff_pay_policies')
    op.drop_index('ix_payroll_configurations_type_location', 'payroll_configurations')
    
    # Drop tables
    op.drop_table('payroll_job_tracking')
    op.drop_table('role_based_pay_rates')
    op.drop_table('tax_approximation_rules')
    op.drop_table('overtime_rules')
    op.drop_table('staff_pay_policies')
    op.drop_table('payroll_configurations')
    
    # Drop enum
    op.execute('DROP TYPE payrollconfigurationtype')