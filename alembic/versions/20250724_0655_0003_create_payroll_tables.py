from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_create_payroll_tables'
down_revision = '0002_create_orders_tables'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'payroll',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_members.id'), nullable=False),
        sa.Column('period', sa.String(), nullable=False),
        sa.Column('gross_pay', sa.Float(), nullable=False),
        sa.Column('deductions', sa.Float(), nullable=False),
        sa.Column('net_pay', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )

    op.create_table(
        'payslips',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('payroll_id', sa.Integer(), sa.ForeignKey('payroll.id'), nullable=False),
        sa.Column('pdf_url', sa.String()),
        sa.Column('issued_at', sa.DateTime(), nullable=False)
    )

def downgrade():
    op.drop_table('payslips')
    op.drop_table('payroll')
