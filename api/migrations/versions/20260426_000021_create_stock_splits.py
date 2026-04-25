"""create stock splits

Revision ID: 20260426_000021
Revises: 20260424_000020
Create Date: 2026-04-26 01:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260426_000021"
down_revision = "20260424_000020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_splits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=True),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("split_factor", sa.Numeric(20, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_code", "ticker", "event_date", name="uq_stock_splits_exchange_ticker_date"),
    )
    op.create_index(op.f("ix_stock_splits_stock_id"), "stock_splits", ["stock_id"], unique=False)
    op.create_index(op.f("ix_stock_splits_exchange_code"), "stock_splits", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_stock_splits_ticker"), "stock_splits", ["ticker"], unique=False)
    op.create_index(op.f("ix_stock_splits_event_date"), "stock_splits", ["event_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_splits_event_date"), table_name="stock_splits")
    op.drop_index(op.f("ix_stock_splits_ticker"), table_name="stock_splits")
    op.drop_index(op.f("ix_stock_splits_exchange_code"), table_name="stock_splits")
    op.drop_index(op.f("ix_stock_splits_stock_id"), table_name="stock_splits")
    op.drop_table("stock_splits")
