from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0005_add_payment_reconciliation'
down_revision = '0004_add_order_tags_categories'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'payment_reconciliations',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'),
                  nullable=False, index=True),
        sa.Column('external_payment_reference', sa.String(),
                  nullable=False, index=True),
        sa.Column('amount_expected', sa.Numeric(10, 2), nullable=False),
        sa.Column('amount_received', sa.Numeric(10, 2), nullable=False),
        sa.Column('reconciliation_status', sa.String(),
                  nullable=False, index=True),
        sa.Column('discrepancy_type', sa.String(), nullable=True, index=True),
        sa.Column('discrepancy_details', sa.Text(), nullable=True),
        sa.Column('reconciliation_action', sa.String(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(),
                  sa.ForeignKey('staff_members.id'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        
        sa.UniqueConstraint('order_id', 'external_payment_reference',
                           name='uq_payment_reconciliation_order_reference')
    )
    
    op.create_index('ix_payment_reconciliations_id',
                    'payment_reconciliations', ['id'])
    op.create_index('ix_payment_reconciliations_order_id',
                    'payment_reconciliations', ['order_id'])
    op.create_index('ix_payment_reconciliations_external_payment_reference',
                    'payment_reconciliations', ['external_payment_reference'])
    op.create_index('ix_payment_reconciliations_reconciliation_status',
                    'payment_reconciliations', ['reconciliation_status'])
    op.create_index('ix_payment_reconciliations_discrepancy_type',
                    'payment_reconciliations', ['discrepancy_type'])
    op.create_index('ix_payment_reconciliations_resolved_by',
                    'payment_reconciliations', ['resolved_by'])


def downgrade():
    op.drop_index('ix_payment_reconciliations_resolved_by',
                  'payment_reconciliations')
    op.drop_index('ix_payment_reconciliations_discrepancy_type',
                  'payment_reconciliations')
    op.drop_index('ix_payment_reconciliations_reconciliation_status',
                  'payment_reconciliations')
    op.drop_index('ix_payment_reconciliations_external_payment_reference',
                  'payment_reconciliations')
    op.drop_index('ix_payment_reconciliations_order_id',
                  'payment_reconciliations')
    op.drop_index('ix_payment_reconciliations_id',
                  'payment_reconciliations')
    op.drop_table('payment_reconciliations')
