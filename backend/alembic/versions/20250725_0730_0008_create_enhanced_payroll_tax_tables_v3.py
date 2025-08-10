"""create_enhanced_payroll_tax_tables_v3

Revision ID: 20250725_0730_0008_v3
Revises: 20250725_0601_0005
Create Date: 2025-07-25 07:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '20250725_0730_0008_v3'
down_revision: Union[str, None] = '20250725_0601_0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Get connection
    connection = op.get_bind()
    
    # Create enum types with existence check using raw SQL
    connection.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paymentstatus') THEN
                CREATE TYPE paymentstatus AS ENUM ('pending', 'calculated', 'approved', 'processed', 'paid', 'cancelled', 'failed');
            END IF;
        END$$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payfrequency') THEN
                CREATE TYPE payfrequency AS ENUM ('weekly', 'biweekly', 'semimonthly', 'monthly');
            END IF;
        END$$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'taxtype') THEN
                CREATE TYPE taxtype AS ENUM ('federal', 'state', 'local', 'social_security', 'medicare', 'unemployment', 'disability', 'workers_comp');
            END IF;
        END$$;
    """))
    
    connection.execute(sa.text("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'paymentmethod') THEN
                CREATE TYPE paymentmethod AS ENUM ('direct_deposit', 'check', 'cash', 'digital_wallet');
            END IF;
        END$$;
    """))

    # Create enhanced payroll_tax_rules table using raw SQL to avoid enum creation issues
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS payroll_tax_rules (
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
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """))
    
    # Create indexes
    op.create_index(op.f('ix_payroll_tax_rules_id'), 'payroll_tax_rules', ['id'], unique=False)
    op.create_index(op.f('ix_payroll_tax_rules_rule_name'), 'payroll_tax_rules', ['rule_name'], unique=False)
    op.create_index(op.f('ix_payroll_tax_rules_location'), 'payroll_tax_rules', ['location'], unique=False)

    # Create enhanced payroll_policies table
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS payroll_policies (
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
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        );
    """))
    
    # Create indexes
    op.create_index(op.f('ix_payroll_policies_id'), 'payroll_policies', ['id'], unique=False)
    op.create_index(op.f('ix_payroll_policies_policy_name'), 'payroll_policies', ['policy_name'], unique=False)
    op.create_index(op.f('ix_payroll_policies_location'), 'payroll_policies', ['location'], unique=False)
    op.create_index('ix_payroll_policies_location_active', 'payroll_policies', ['location', 'is_active'])
    op.create_index('ix_payroll_policies_tenant_location', 'payroll_policies', ['tenant_id', 'location'])

    # Create enhanced employee_payments table
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS employee_payments (
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
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_employee_payment_period UNIQUE (staff_id, pay_period_start, pay_period_end)
        );
    """))
    
    # Create indexes
    op.create_index(op.f('ix_employee_payments_id'), 'employee_payments', ['id'], unique=False)
    op.create_index(op.f('ix_employee_payments_staff_id'), 'employee_payments', ['staff_id'], unique=False)
    op.create_index('ix_employee_payments_staff_period', 'employee_payments', ['staff_id', 'pay_period_start', 'pay_period_end'])
    op.create_index('ix_employee_payments_pay_date', 'employee_payments', ['pay_date'])
    op.create_index('ix_employee_payments_status', 'employee_payments', ['payment_status'])
    op.create_index('ix_employee_payments_tenant_staff', 'employee_payments', ['tenant_id', 'staff_id'])

    # Create employee_payment_tax_applications table
    connection.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS employee_payment_tax_applications (
            id SERIAL PRIMARY KEY,
            employee_payment_id INTEGER NOT NULL REFERENCES employee_payments(id),
            tax_rule_id INTEGER NOT NULL REFERENCES payroll_tax_rules(id),
            taxable_amount NUMERIC(12, 2) NOT NULL,
            calculated_tax NUMERIC(12, 2) NOT NULL,
            effective_rate NUMERIC(5, 4) NOT NULL,
            calculation_date TIMESTAMP NOT NULL,
            calculation_method VARCHAR(50),
            notes TEXT,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_payment_tax_rule UNIQUE (employee_payment_id, tax_rule_id)
        );
    """))
    
    # Create indexes
    op.create_index(op.f('ix_employee_payment_tax_applications_id'), 'employee_payment_tax_applications', ['id'], unique=False)
    op.create_index('ix_tax_applications_payment_id', 'employee_payment_tax_applications', ['employee_payment_id'])
    op.create_index('ix_tax_applications_tax_rule_id', 'employee_payment_tax_applications', ['tax_rule_id'])
    op.create_index('ix_tax_applications_calculation_date', 'employee_payment_tax_applications', ['calculation_date'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('employee_payment_tax_applications')
    op.drop_table('employee_payments')
    op.drop_table('payroll_policies')
    op.drop_table('payroll_tax_rules')
    
    # Drop enum types using raw SQL with existence check
    connection = op.get_bind()
    connection.execute(sa.text("DROP TYPE IF EXISTS paymentmethod"))
    connection.execute(sa.text("DROP TYPE IF EXISTS taxtype"))
    connection.execute(sa.text("DROP TYPE IF EXISTS payfrequency"))
    connection.execute(sa.text("DROP TYPE IF EXISTS paymentstatus"))