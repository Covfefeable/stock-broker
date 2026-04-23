"""create stock daily bars

Revision ID: 20260424_000007
Revises: 20260424_000006
Create Date: 2026-04-24 00:00:07

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000007"
down_revision = "20260424_000006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stock_daily_bars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=True),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("high", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("low", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("close", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange_code",
            "ticker",
            "trade_date",
            name="uq_stock_daily_bars_exchange_ticker_date",
        ),
    )
    op.create_index(op.f("ix_stock_daily_bars_exchange_code"), "stock_daily_bars", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_stock_daily_bars_stock_id"), "stock_daily_bars", ["stock_id"], unique=False)
    op.create_index(op.f("ix_stock_daily_bars_ticker"), "stock_daily_bars", ["ticker"], unique=False)
    op.create_index(op.f("ix_stock_daily_bars_trade_date"), "stock_daily_bars", ["trade_date"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_stock_daily_bars_trade_date"), table_name="stock_daily_bars")
    op.drop_index(op.f("ix_stock_daily_bars_ticker"), table_name="stock_daily_bars")
    op.drop_index(op.f("ix_stock_daily_bars_stock_id"), table_name="stock_daily_bars")
    op.drop_index(op.f("ix_stock_daily_bars_exchange_code"), table_name="stock_daily_bars")
    op.drop_table("stock_daily_bars")
