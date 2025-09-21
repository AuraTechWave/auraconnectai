"""Align order ORM with service expectations

Revision ID: 20250201_1100_align_order_model_fields
Revises: add_inventory_deduction_tracking
Create Date: 2025-02-01 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250201_1100_align_order_model_fields"
down_revision = "add_inventory_deduction_tracking"
branch_labels = None
depends_on = None


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _index_exists(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Orders table adjustments
    if not _column_exists(inspector, "orders", "completed_at"):
        op.add_column("orders", sa.Column("completed_at", sa.DateTime(), nullable=True))

    if not _column_exists(inspector, "orders", "completed_by_id"):
        op.add_column(
            "orders",
            sa.Column(
                "completed_by_id",
                sa.Integer(),
                sa.ForeignKey("staff_members.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_orders_completed_by_id",
            "orders",
            ["completed_by_id"],
            unique=False,
        )

    if not _column_exists(inspector, "orders", "cancelled_at"):
        op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(), nullable=True))

    if not _column_exists(inspector, "orders", "cancelled_by_id"):
        op.add_column(
            "orders",
            sa.Column(
                "cancelled_by_id",
                sa.Integer(),
                sa.ForeignKey("staff_members.id"),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_orders_cancelled_by_id",
            "orders",
            ["cancelled_by_id"],
            unique=False,
        )

    if not _column_exists(inspector, "orders", "cancellation_reason"):
        op.add_column(
            "orders", sa.Column("cancellation_reason", sa.Text(), nullable=True)
        )

    if not _column_exists(inspector, "orders", "is_cancelled"):
        op.add_column(
            "orders",
            sa.Column(
                "is_cancelled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        # Ensure existing cancelled orders are marked appropriately
        op.execute(
            "UPDATE orders SET is_cancelled = true WHERE status = 'CANCELLED'"
        )
        op.alter_column(
            "orders",
            "is_cancelled",
            server_default=None,
            existing_type=sa.Boolean(),
        )

    if not _column_exists(inspector, "orders", "metadata"):
        op.add_column(
            "orders",
            sa.Column(
                "metadata",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
        op.alter_column(
            "orders",
            "metadata",
            server_default=None,
            existing_type=postgresql.JSONB(astext_type=sa.Text()),
        )

    # Order items table adjustments
    if not _column_exists(inspector, "order_items", "is_cancelled"):
        op.add_column(
            "order_items",
            sa.Column(
                "is_cancelled",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        op.execute("UPDATE order_items SET is_cancelled = false")
        op.alter_column(
            "order_items",
            "is_cancelled",
            server_default=None,
            existing_type=sa.Boolean(),
        )
        if not _index_exists(inspector, "order_items", "ix_order_items_is_cancelled"):
            op.create_index(
                "ix_order_items_is_cancelled",
                "order_items",
                ["is_cancelled"],
                unique=False,
            )

    # Helpful indexes for querying completion/cancellation timelines
    if not _index_exists(inspector, "orders", "ix_orders_completed_at"):
        op.create_index(
            "ix_orders_completed_at", "orders", ["completed_at"], unique=False
        )

    if not _index_exists(inspector, "orders", "ix_orders_cancelled_at"):
        op.create_index(
            "ix_orders_cancelled_at", "orders", ["cancelled_at"], unique=False
        )


def downgrade() -> None:
    # Drop indexes and columns added in upgrade
    op.drop_index("ix_orders_cancelled_at", table_name="orders", if_exists=True)
    op.drop_index("ix_orders_completed_at", table_name="orders", if_exists=True)
    op.drop_index("ix_order_items_is_cancelled", table_name="order_items", if_exists=True)
    op.drop_index("ix_orders_cancelled_by_id", table_name="orders", if_exists=True)
    op.drop_index("ix_orders_completed_by_id", table_name="orders", if_exists=True)

    op.drop_column("order_items", "is_cancelled", if_exists=True)

    op.drop_column("orders", "metadata", if_exists=True)
    op.drop_column("orders", "is_cancelled", if_exists=True)
    op.drop_column("orders", "cancellation_reason", if_exists=True)
    op.drop_column("orders", "cancelled_by_id", if_exists=True)
    op.drop_column("orders", "cancelled_at", if_exists=True)
    op.drop_column("orders", "completed_by_id", if_exists=True)
    op.drop_column("orders", "completed_at", if_exists=True)
