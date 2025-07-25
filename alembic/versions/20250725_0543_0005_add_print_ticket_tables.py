from alembic import op
import sqlalchemy as sa

revision = '0005_add_print_ticket_tables'
down_revision = '0004_add_order_tags_categories'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        'print_stations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('ticket_types', sa.String(), nullable=False),
        sa.Column('printer_config', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_print_stations_id', 'print_stations', ['id'])
    op.create_index('ix_print_stations_name', 'print_stations', ['name'])
    op.create_index('ix_print_stations_is_active', 'print_stations', ['is_active'])
    
    op.create_table(
        'print_tickets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('ticket_type', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, default='pending'),
        sa.Column('station_id', sa.Integer(), sa.ForeignKey('print_stations.id'), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, default=1),
        sa.Column('ticket_content', sa.Text(), nullable=False),
        sa.Column('printed_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), default=0),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False)
    )
    
    op.create_index('ix_print_tickets_id', 'print_tickets', ['id'])
    op.create_index('ix_print_tickets_order_id', 'print_tickets', ['order_id'])
    op.create_index('ix_print_tickets_ticket_type', 'print_tickets', ['ticket_type'])
    op.create_index('ix_print_tickets_status', 'print_tickets', ['status'])
    op.create_index('ix_print_tickets_station_id', 'print_tickets', ['station_id'])

def downgrade():
    op.drop_index('ix_print_tickets_station_id', 'print_tickets')
    op.drop_index('ix_print_tickets_status', 'print_tickets')
    op.drop_index('ix_print_tickets_ticket_type', 'print_tickets')
    op.drop_index('ix_print_tickets_order_id', 'print_tickets')
    op.drop_index('ix_print_tickets_id', 'print_tickets')
    op.drop_table('print_tickets')
    op.drop_index('ix_print_stations_is_active', 'print_stations')
    op.drop_index('ix_print_stations_name', 'print_stations')
    op.drop_index('ix_print_stations_id', 'print_stations')
    op.drop_table('print_stations')
