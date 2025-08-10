"""Create payroll tax tables - final

Revision ID: 20250810_1000_payroll_tax_tables
Revises: 20250725_0601_0005
Create Date: 2025-08-10 10:00:00.000000

This migration handles enum creation gracefully and avoids conflicts.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20250810_1000_payroll_tax_tables'
down_revision: Union[str, None] = '20250725_0601_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection
    connection = op.get_bind()
    
    # First, let's check what enums already exist
    existing_enums = connection.execute(sa.text("""
        SELECT typname FROM pg_type WHERE typtype = 'e'
    """)).fetchall()
    existing_enum_names = [row[0] for row in existing_enums]
    
    # Create enums only if they don't exist
    if 'paymentstatus' not in existing_enum_names:
        connection.execute(sa.text("""
            CREATE TYPE paymentstatus AS ENUM ('pending', 'calculated', 'approved', 'processed', 'paid', 'cancelled', 'failed')
        """))
    
    if 'payfrequency' not in existing_enum_names:
        connection.execute(sa.text("""
            CREATE TYPE payfrequency AS ENUM ('weekly', 'biweekly', 'semimonthly', 'monthly')
        """))
    
    if 'taxtype' not in existing_enum_names:
        connection.execute(sa.text("""
            CREATE TYPE taxtype AS ENUM ('federal', 'state', 'local', 'social_security', 'medicare', 'unemployment', 'disability', 'workers_comp')
        """))
    
    if 'paymentmethod' not in existing_enum_names:
        connection.execute(sa.text("""
            CREATE TYPE paymentmethod AS ENUM ('direct_deposit', 'check', 'cash', 'digital_wallet')
        """))
    
    # Check if tables already exist
    existing_tables = connection.execute(sa.text("""
        SELECT tablename FROM pg_tables WHERE schemaname = 'public'
    """)).fetchall()
    existing_table_names = [row[0] for row in existing_tables]
    
    # Create payroll_tax_rules table if it doesn't exist
    if 'payroll_tax_rules' not in existing_table_names:
        connection.execute(sa.text("""
            CREATE TABLE payroll_tax_rules (
                id SERIAL PRIMARY KEY,
                rule_name VARCHAR(100) NOT NULL,
                location VARCHAR(100) NOT NULL,
                tax_type taxtype NOT NULL,
                rate_percent NUMERIC(5, 4) NOT NULL,
                max_taxable_amount NUMERIC(12, 2),
                min_taxable_amount NUMERIC(12, 2),
                employee_portion NUMERIC(5, 4),
                employer_portion NUMERIC(5, 4),
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                tenant_id INTEGER,
                effective_date TIMESTAMP NOT NULL,
                expiry_date TIMESTAMP,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create indexes
        connection.execute(sa.text("CREATE INDEX ix_payroll_tax_rules_id ON payroll_tax_rules(id)"))
        connection.execute(sa.text("CREATE INDEX ix_payroll_tax_rules_rule_name ON payroll_tax_rules(rule_name)"))
        connection.execute(sa.text("CREATE INDEX ix_payroll_tax_rules_location ON payroll_tax_rules(location)"))
    
    # Create payroll_policies table if it doesn't exist
    if 'payroll_policies' not in existing_table_names:
        connection.execute(sa.text("""
            CREATE TABLE payroll_policies (
                id SERIAL PRIMARY KEY,
                policy_name VARCHAR(100) NOT NULL,
                location VARCHAR(100) NOT NULL,
                pay_frequency payfrequency NOT NULL,
                overtime_threshold_hours NUMERIC(6, 2) NOT NULL DEFAULT 40.00,
                overtime_multiplier NUMERIC(5, 4) NOT NULL DEFAULT 1.5000,
                double_time_threshold_hours NUMERIC(6, 2),
                double_time_multiplier NUMERIC(5, 4) DEFAULT 2.0000,
                pay_period_start_day INTEGER NOT NULL,
                minimum_wage NUMERIC(8, 2) NOT NULL,
                meal_break_threshold_hours NUMERIC(6, 2) DEFAULT 5.00,
                rest_break_threshold_hours NUMERIC(6, 2) DEFAULT 4.00,
                holiday_pay_multiplier NUMERIC(5, 4) DEFAULT 1.5000,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                tenant_id INTEGER,
                description TEXT,
                is_active BOOLEAN NOT NULL DEFAULT true,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        
        # Create indexes
        connection.execute(sa.text("CREATE INDEX ix_payroll_policies_id ON payroll_policies(id)"))
        connection.execute(sa.text("CREATE INDEX ix_payroll_policies_policy_name ON payroll_policies(policy_name)"))
        connection.execute(sa.text("CREATE INDEX ix_payroll_policies_location ON payroll_policies(location)"))
        connection.execute(sa.text("CREATE INDEX ix_payroll_policies_location_active ON payroll_policies(location, is_active)"))
        connection.execute(sa.text("CREATE INDEX ix_payroll_policies_tenant_location ON payroll_policies(tenant_id, location)"))
    
    # Create employee_payments table if it doesn't exist
    if 'employee_payments' not in existing_table_names:
        connection.execute(sa.text("""
            CREATE TABLE employee_payments (
                id SERIAL PRIMARY KEY,
                staff_id INTEGER NOT NULL,
                payroll_policy_id INTEGER NOT NULL REFERENCES payroll_policies(id),
                pay_period_start TIMESTAMP NOT NULL,
                pay_period_end TIMESTAMP NOT NULL,
                pay_date TIMESTAMP NOT NULL,
                regular_hours NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
                overtime_hours NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
                double_time_hours NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
                holiday_hours NUMERIC(6, 2) NOT NULL DEFAULT 0.00,
                regular_rate NUMERIC(10, 4) NOT NULL,
                overtime_rate NUMERIC(10, 4),
                double_time_rate NUMERIC(10, 4),
                holiday_rate NUMERIC(10, 4),
                regular_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                overtime_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                double_time_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                holiday_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                bonus_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                commission_pay NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                gross_pay NUMERIC(12, 2) NOT NULL,
                federal_tax NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                state_tax NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                local_tax NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                social_security_tax NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                medicare_tax NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                insurance_deduction NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                retirement_deduction NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                other_deductions NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
                total_deductions NUMERIC(12, 2) NOT NULL,
                net_pay NUMERIC(12, 2) NOT NULL,
                currency VARCHAR(3) NOT NULL DEFAULT 'USD',
                tenant_id INTEGER,
                payment_status paymentstatus NOT NULL DEFAULT 'pending',
                payment_method paymentmethod,
                notes TEXT,
                processed_by VARCHAR(100),
                processed_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_employee_payment_period UNIQUE (staff_id, pay_period_start, pay_period_end)
            )
        """))
        
        # Create indexes
        connection.execute(sa.text("CREATE INDEX ix_employee_payments_id ON employee_payments(id)"))
        connection.execute(sa.text("CREATE INDEX ix_employee_payments_staff_id ON employee_payments(staff_id)"))
        connection.execute(sa.text("CREATE INDEX ix_employee_payments_staff_period ON employee_payments(staff_id, pay_period_start, pay_period_end)"))
        connection.execute(sa.text("CREATE INDEX ix_employee_payments_pay_date ON employee_payments(pay_date)"))
        connection.execute(sa.text("CREATE INDEX ix_employee_payments_status ON employee_payments(payment_status)"))
        connection.execute(sa.text("CREATE INDEX ix_employee_payments_tenant_staff ON employee_payments(tenant_id, staff_id)"))
    
    # Create employee_payment_tax_applications table if it doesn't exist
    if 'employee_payment_tax_applications' not in existing_table_names:
        connection.execute(sa.text("""
            CREATE TABLE employee_payment_tax_applications (
                id SERIAL PRIMARY KEY,
                employee_payment_id INTEGER NOT NULL REFERENCES employee_payments(id),
                tax_rule_id INTEGER NOT NULL REFERENCES payroll_tax_rules(id),
                taxable_amount NUMERIC(12, 2) NOT NULL,
                calculated_tax NUMERIC(12, 2) NOT NULL,
                effective_rate NUMERIC(5, 4) NOT NULL,
                calculation_date TIMESTAMP NOT NULL,
                calculation_method VARCHAR(50),
                notes TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_payment_tax_rule UNIQUE (employee_payment_id, tax_rule_id)
            )
        """))
        
        # Create indexes
        connection.execute(sa.text("CREATE INDEX ix_employee_payment_tax_applications_id ON employee_payment_tax_applications(id)"))
        connection.execute(sa.text("CREATE INDEX ix_tax_applications_payment_id ON employee_payment_tax_applications(employee_payment_id)"))
        connection.execute(sa.text("CREATE INDEX ix_tax_applications_tax_rule_id ON employee_payment_tax_applications(tax_rule_id)"))
        connection.execute(sa.text("CREATE INDEX ix_tax_applications_calculation_date ON employee_payment_tax_applications(calculation_date)"))


def downgrade() -> None:
    # Get connection
    connection = op.get_bind()
    
    # Drop tables if they exist
    connection.execute(sa.text("DROP TABLE IF EXISTS employee_payment_tax_applications CASCADE"))
    connection.execute(sa.text("DROP TABLE IF EXISTS employee_payments CASCADE"))
    connection.execute(sa.text("DROP TABLE IF EXISTS payroll_policies CASCADE"))
    connection.execute(sa.text("DROP TABLE IF EXISTS payroll_tax_rules CASCADE"))
    
    # Drop enum types if they exist
    connection.execute(sa.text("DROP TYPE IF EXISTS paymentmethod CASCADE"))
    connection.execute(sa.text("DROP TYPE IF EXISTS taxtype CASCADE"))
    connection.execute(sa.text("DROP TYPE IF EXISTS payfrequency CASCADE"))
    connection.execute(sa.text("DROP TYPE IF EXISTS paymentstatus CASCADE"))