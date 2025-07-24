from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0003_create_tax_tables'
down_revision = '0002_create_orders_tables'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'tax_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('location', sa.String(), nullable=False, index=True),
        sa.Column('category', sa.String(), nullable=False, index=True),
        sa.Column('rate_percent', sa.Numeric(5, 4), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('idx_tax_rules_location_category', 'tax_rules', ['location', 'category'])

def downgrade():
    op.drop_table('tax_rules')
