from alembic import op
import sqlalchemy as sa
from datetime import datetime

revision = '0003_create_pos_sync_settings'
down_revision = '0002_create_orders_tables'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'pos_sync_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), nullable=True),
        sa.Column('team_id', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('staff_members.id'), nullable=False)
    )
    
    op.create_unique_constraint('uq_pos_sync_tenant_team', 'pos_sync_settings', ['tenant_id', 'team_id'])
    
    op.create_index('idx_pos_sync_tenant', 'pos_sync_settings', ['tenant_id'])
    op.create_index('idx_pos_sync_team', 'pos_sync_settings', ['team_id'])

def downgrade():
    op.drop_table('pos_sync_settings')
