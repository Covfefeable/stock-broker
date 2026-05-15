"""create etfs

Revision ID: 20260516_000034
Revises: 20260430_000033
Create Date: 2026-05-16 02:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20260516_000034"
down_revision = "20260430_000033"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "etfs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("exchange_id", sa.Integer(), nullable=True),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"]),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchanges.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_code", "ticker", name="uq_etfs_exchange_ticker"),
    )
    op.create_index(op.f("ix_etfs_country_code"), "etfs", ["country_code"], unique=False)
    op.create_index(op.f("ix_etfs_country_id"), "etfs", ["country_id"], unique=False)
    op.create_index(op.f("ix_etfs_exchange_code"), "etfs", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_etfs_exchange_id"), "etfs", ["exchange_id"], unique=False)

    op.create_table(
        "etf_daily_bars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("etf_id", sa.Integer(), nullable=True),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("high", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("low", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("close", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("volume", sa.Numeric(precision=24, scale=6), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["etf_id"], ["etfs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "exchange_code",
            "ticker",
            "trade_date",
            name="uq_etf_daily_bars_exchange_ticker_date",
        ),
    )
    op.create_index(op.f("ix_etf_daily_bars_etf_id"), "etf_daily_bars", ["etf_id"], unique=False)
    op.create_index(op.f("ix_etf_daily_bars_exchange_code"), "etf_daily_bars", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_etf_daily_bars_ticker"), "etf_daily_bars", ["ticker"], unique=False)
    op.create_index(op.f("ix_etf_daily_bars_trade_date"), "etf_daily_bars", ["trade_date"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_etf_daily_bars_trade_date"), table_name="etf_daily_bars")
    op.drop_index(op.f("ix_etf_daily_bars_ticker"), table_name="etf_daily_bars")
    op.drop_index(op.f("ix_etf_daily_bars_exchange_code"), table_name="etf_daily_bars")
    op.drop_index(op.f("ix_etf_daily_bars_etf_id"), table_name="etf_daily_bars")
    op.drop_table("etf_daily_bars")
    op.drop_index(op.f("ix_etfs_exchange_id"), table_name="etfs")
    op.drop_index(op.f("ix_etfs_exchange_code"), table_name="etfs")
    op.drop_index(op.f("ix_etfs_country_id"), table_name="etfs")
    op.drop_index(op.f("ix_etfs_country_code"), table_name="etfs")
    op.drop_table("etfs")
