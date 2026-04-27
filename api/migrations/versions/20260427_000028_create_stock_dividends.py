"""create stock dividends

Revision ID: 20260427_000028
Revises: 20260426_000027
Create Date: 2026-04-27 19:30:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260427_000028"
down_revision = "20260426_000027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_dividends",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=True),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("dividend", sa.Numeric(20, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange_code", "ticker", "event_date", name="uq_stock_dividends_exchange_ticker_date"
        ),
    )
    op.create_index(
        op.f("ix_stock_dividends_stock_id"), "stock_dividends", ["stock_id"], unique=False
    )
    op.create_index(
        op.f("ix_stock_dividends_exchange_code"), "stock_dividends", ["exchange_code"], unique=False
    )
    op.create_index(op.f("ix_stock_dividends_ticker"), "stock_dividends", ["ticker"], unique=False)
    op.create_index(
        op.f("ix_stock_dividends_event_date"), "stock_dividends", ["event_date"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stock_dividends_event_date"), table_name="stock_dividends")
    op.drop_index(op.f("ix_stock_dividends_ticker"), table_name="stock_dividends")
    op.drop_index(op.f("ix_stock_dividends_exchange_code"), table_name="stock_dividends")
    op.drop_index(op.f("ix_stock_dividends_stock_id"), table_name="stock_dividends")
    op.drop_table("stock_dividends")
