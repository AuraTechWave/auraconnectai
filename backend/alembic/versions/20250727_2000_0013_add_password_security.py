"""Add password security tables and features

Revision ID: 0013_add_password_security
Revises: 0012_create_rbac_tables
Create Date: 2025-07-27 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '0013_add_password_security'
down_revision = '0012_create_rbac_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Add password security tables and enhance existing ones."""
    
    # Create password_reset_tokens table
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('is_used', sa.Boolean(), nullable=False, default=False),
        sa.Column('attempt_count', sa.Integer(), nullable=False, default=0),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for password_reset_tokens
    op.create_index('ix_password_reset_tokens_id', 'password_reset_tokens', ['id'])
    op.create_index('ix_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True)
    op.create_index('ix_password_reset_tokens_user_id', 'password_reset_tokens', ['user_id'])
    op.create_index('ix_password_reset_tokens_email', 'password_reset_tokens', ['email'])
    op.create_index('ix_password_reset_tokens_expires_at', 'password_reset_tokens', ['expires_at'])
    op.create_index('ix_password_reset_tokens_is_used', 'password_reset_tokens', ['is_used'])
    
    # Composite indexes for performance
    op.create_index('idx_password_reset_user_active', 'password_reset_tokens', ['user_id', 'is_used', 'expires_at'])
    op.create_index('idx_password_reset_email_active', 'password_reset_tokens', ['email', 'is_used', 'expires_at'])
    op.create_index('idx_password_reset_cleanup', 'password_reset_tokens', ['expires_at', 'is_used'])
    
    # Create password_history table
    op.create_table(
        'password_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('algorithm', sa.String(length=50), nullable=False),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for password_history
    op.create_index('ix_password_history_id', 'password_history', ['id'])
    op.create_index('ix_password_history_user_id', 'password_history', ['user_id'])
    op.create_index('idx_password_history_user_created', 'password_history', ['user_id', 'created_at'])
    op.create_index('idx_password_history_cleanup', 'password_history', ['created_at'])
    
    # Create security_audit_logs table
    op.create_table(
        'security_audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_details', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, default=datetime.utcnow),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('risk_score', sa.Integer(), nullable=False, default=0),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['rbac_users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for security_audit_logs
    op.create_index('ix_security_audit_logs_id', 'security_audit_logs', ['id'])
    op.create_index('ix_security_audit_logs_user_id', 'security_audit_logs', ['user_id'])
    op.create_index('ix_security_audit_logs_event_type', 'security_audit_logs', ['event_type'])
    op.create_index('ix_security_audit_logs_timestamp', 'security_audit_logs', ['timestamp'])
    op.create_index('ix_security_audit_logs_ip_address', 'security_audit_logs', ['ip_address'])
    op.create_index('ix_security_audit_logs_success', 'security_audit_logs', ['success'])
    op.create_index('ix_security_audit_logs_email', 'security_audit_logs', ['email'])
    
    # Composite indexes for performance and security monitoring
    op.create_index('idx_security_audit_user_event', 'security_audit_logs', ['user_id', 'event_type', 'timestamp'])
    op.create_index('idx_security_audit_ip_event', 'security_audit_logs', ['ip_address', 'event_type', 'timestamp'])
    op.create_index('idx_security_audit_email_event', 'security_audit_logs', ['email', 'event_type', 'timestamp'])
    op.create_index('idx_security_audit_risk', 'security_audit_logs', ['risk_score', 'timestamp'])
    op.create_index('idx_security_audit_failed', 'security_audit_logs', ['success', 'timestamp'])
    
    # Add new columns to rbac_users table for enhanced security
    op.add_column('rbac_users', sa.Column('password_changed_at', sa.DateTime(), nullable=True))
    op.add_column('rbac_users', sa.Column('password_reset_required', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('rbac_users', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('rbac_users', sa.Column('locked_until', sa.DateTime(), nullable=True))
    op.add_column('rbac_users', sa.Column('last_password_reset', sa.DateTime(), nullable=True))
    
    # Create indexes for new columns
    op.create_index('ix_rbac_users_password_changed_at', 'rbac_users', ['password_changed_at'])
    op.create_index('ix_rbac_users_password_reset_required', 'rbac_users', ['password_reset_required'])
    op.create_index('ix_rbac_users_locked_until', 'rbac_users', ['locked_until'])
    
    # Update existing users to set password_changed_at to created_at
    connection = op.get_bind()
    connection.execute(
        sa.text("""
            UPDATE rbac_users 
            SET password_changed_at = created_at 
            WHERE password_changed_at IS NULL
        """)
    )


def downgrade():
    """Remove password security tables and columns."""
    
    # Remove new columns from rbac_users
    op.drop_index('ix_rbac_users_locked_until', table_name='rbac_users')
    op.drop_index('ix_rbac_users_password_reset_required', table_name='rbac_users')
    op.drop_index('ix_rbac_users_password_changed_at', table_name='rbac_users')
    
    op.drop_column('rbac_users', 'last_password_reset')
    op.drop_column('rbac_users', 'locked_until')
    op.drop_column('rbac_users', 'failed_login_attempts')
    op.drop_column('rbac_users', 'password_reset_required')
    op.drop_column('rbac_users', 'password_changed_at')
    
    # Drop security_audit_logs table
    op.drop_index('idx_security_audit_failed', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_risk', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_email_event', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_ip_event', table_name='security_audit_logs')
    op.drop_index('idx_security_audit_user_event', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_email', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_success', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_ip_address', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_timestamp', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_event_type', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_user_id', table_name='security_audit_logs')
    op.drop_index('ix_security_audit_logs_id', table_name='security_audit_logs')
    op.drop_table('security_audit_logs')
    
    # Drop password_history table
    op.drop_index('idx_password_history_cleanup', table_name='password_history')
    op.drop_index('idx_password_history_user_created', table_name='password_history')
    op.drop_index('ix_password_history_user_id', table_name='password_history')
    op.drop_index('ix_password_history_id', table_name='password_history')
    op.drop_table('password_history')
    
    # Drop password_reset_tokens table
    op.drop_index('idx_password_reset_cleanup', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_email_active', table_name='password_reset_tokens')
    op.drop_index('idx_password_reset_user_active', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_is_used', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_expires_at', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_email', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_user_id', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_token_hash', table_name='password_reset_tokens')
    op.drop_index('ix_password_reset_tokens_id', table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')