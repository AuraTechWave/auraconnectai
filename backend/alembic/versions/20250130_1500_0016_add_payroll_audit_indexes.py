"""Add payroll audit indexes for performance optimization

Revision ID: 0016
Revises: 0015
Create Date: 2025-01-30 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250130_1500_0016'
down_revision = '20250727_2200_0015'
branch_labels = None
depends_on = None


def upgrade():
    # Create optimized indexes for audit log queries
    
    # Index for date range queries (most common)
    op.create_index(
        'idx_audit_timestamp_covering',
        'payroll_audit_logs',
        ['timestamp', 'event_type', 'user_id'],
        postgresql_using='btree'
    )
    
    # Index for event type filtering with date
    op.create_index(
        'idx_audit_event_date',
        'payroll_audit_logs',
        ['event_type', 'timestamp'],
        postgresql_using='btree'
    )
    
    # Index for user activity queries
    op.create_index(
        'idx_audit_user_activity',
        'payroll_audit_logs',
        ['user_id', 'timestamp', 'event_type'],
        postgresql_using='btree'
    )
    
    # Index for entity-specific queries
    op.create_index(
        'idx_audit_entity_lookup',
        'payroll_audit_logs',
        ['entity_type', 'entity_id', 'timestamp'],
        postgresql_using='btree'
    )
    
    # Index for tenant isolation with timestamp
    op.create_index(
        'idx_audit_tenant_date',
        'payroll_audit_logs',
        ['tenant_id', 'timestamp'],
        postgresql_using='btree',
        postgresql_where=sa.text('tenant_id IS NOT NULL')
    )
    
    # Partial index for access denied events (compliance)
    op.create_index(
        'idx_audit_access_denied',
        'payroll_audit_logs',
        ['timestamp', 'user_id'],
        postgresql_using='btree',
        postgresql_where=sa.text("event_type = 'access.denied'")
    )
    
    # Index for session tracking
    op.create_index(
        'idx_audit_session',
        'payroll_audit_logs',
        ['session_id', 'timestamp'],
        postgresql_using='btree',
        postgresql_where=sa.text('session_id IS NOT NULL')
    )
    
    # Create indexes for batch job tracking
    op.create_index(
        'idx_job_status_type',
        'payroll_job_tracking',
        ['status', 'job_type', 'started_at'],
        postgresql_using='btree'
    )
    
    op.create_index(
        'idx_job_tenant_status',
        'payroll_job_tracking',
        ['tenant_id', 'status', 'started_at'],
        postgresql_using='btree',
        postgresql_where=sa.text('tenant_id IS NOT NULL')
    )
    
    # Create indexes for webhook subscriptions
    op.create_index(
        'idx_webhook_active',
        'payroll_webhook_subscriptions',
        ['is_active', 'tenant_id'],
        postgresql_using='btree',
        postgresql_where=sa.text('is_active = true')
    )
    
    # Add table partitioning comment (for future implementation)
    op.execute("""
        COMMENT ON TABLE payroll_audit_logs IS 
        'Audit trail for payroll operations. Consider partitioning by timestamp for tables > 100M rows.';
    """)
    

def downgrade():
    # Drop indexes in reverse order
    op.drop_index('idx_webhook_active', 'payroll_webhook_subscriptions')
    op.drop_index('idx_job_tenant_status', 'payroll_job_tracking')
    op.drop_index('idx_job_status_type', 'payroll_job_tracking')
    op.drop_index('idx_audit_session', 'payroll_audit_logs')
    op.drop_index('idx_audit_access_denied', 'payroll_audit_logs')
    op.drop_index('idx_audit_tenant_date', 'payroll_audit_logs')
    op.drop_index('idx_audit_entity_lookup', 'payroll_audit_logs')
    op.drop_index('idx_audit_user_activity', 'payroll_audit_logs')
    op.drop_index('idx_audit_event_date', 'payroll_audit_logs')
    op.drop_index('idx_audit_timestamp_covering', 'payroll_audit_logs')