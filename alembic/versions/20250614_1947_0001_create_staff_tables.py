
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_create_staff_tables'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'roles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), unique=True, nullable=False),
        sa.Column('permissions', sa.String())
    )

    op.create_table(
        'staff_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), unique=True),
        sa.Column('phone', sa.String()),
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id')),
        sa.Column('status', sa.String()),
        sa.Column('start_date', sa.DateTime()),
        sa.Column('photo_url', sa.String())
    )

    op.create_table(
        'shifts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_members.id')),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('date', sa.DateTime(), nullable=False),
        sa.Column('location_id', sa.Integer())
    )

    op.create_table(
        'attendance_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('staff_id', sa.Integer(), sa.ForeignKey('staff_members.id')),
        sa.Column('check_in', sa.DateTime()),
        sa.Column('check_out', sa.DateTime()),
        sa.Column('method', sa.String()),
        sa.Column('status', sa.String())
    )

def downgrade():
    op.drop_table('attendance_logs')
    op.drop_table('shifts')
    op.drop_table('staff_members')
    op.drop_table('roles')
