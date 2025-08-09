from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0005_add_payment_reconciliation'
down_revision = '0004_add_order_tags_categories'
branch_labels = None
depends_on = None


def upgrade():
    reconciliation_status_enum = postgresql.ENUM(
        'pending', 'matched', 'discrepancy', 'resolved',
        name='reconciliationstatus'
    )
    reconciliation_status_enum.create(op.get_bind())

    discrepancy_type_enum = postgresql.ENUM(
        'amount_mismatch', 'missing_payment', 'duplicate_payment',
        name='discrepancytype'
    )
    discrepancy_type_enum.create(op.get_bind())

    reconciliation_action_enum = postgresql.ENUM(
        'auto_matched', 'manual_review', 'exception_handled',
        name='reconciliationaction'
    )
    reconciliation_action_enum.create(op.get_bind())

    op.create_table(
        'payment_reconciliations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'),
                  nullable=False),
        sa.Column('external_payment_reference', sa.String(),
                  nullable=False),
        sa.Column('amount_expected', sa.Numeric(10, 2), nullable=False),
        sa.Column('amount_received', sa.Numeric(10, 2), nullable=False),
        sa.Column('reconciliation_status', reconciliation_status_enum,
                  nullable=False),
        sa.Column('discrepancy_type', discrepancy_type_enum, nullable=True),
        sa.Column('discrepancy_details', sa.Text(), nullable=True),
        sa.Column('reconciliation_action', reconciliation_action_enum,
                  nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.Integer(),
                  sa.ForeignKey('staff_members.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  onupdate=sa.text('now()')),

        sa.UniqueConstraint('order_id', 'external_payment_reference',
                           name='uq_payment_reconciliation_order_reference')
    )

    op.create_index('ix_payment_reconciliations_order_id',
                    'payment_reconciliations', ['order_id'])
    op.create_index('ix_payment_reconciliations_status',
                    'payment_reconciliations', ['reconciliation_status'])
    op.create_index('ix_payment_reconciliations_reference',
                    'payment_reconciliations', ['external_payment_reference'])


def downgrade():
    op.drop_table('payment_reconciliations')
    op.execute('DROP TYPE IF EXISTS reconciliationaction')
    op.execute('DROP TYPE IF EXISTS discrepancytype')
    op.execute('DROP TYPE IF EXISTS reconciliationstatus')
