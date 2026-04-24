"""create index daily bars

Revision ID: 20260424_000012
Revises: 20260424_000011
Create Date: 2026-04-24 08:50:00

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000012"
down_revision = "20260424_000011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "index_daily_bars",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("index_asset_id", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("open", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("high", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("low", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("close", sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column("volume", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["index_asset_id"], ["index_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "country_code",
            "ticker",
            "trade_date",
            name="uq_index_daily_bars_country_ticker_date",
        ),
    )
    op.create_index(op.f("ix_index_daily_bars_country_code"), "index_daily_bars", ["country_code"], unique=False)
    op.create_index(op.f("ix_index_daily_bars_index_asset_id"), "index_daily_bars", ["index_asset_id"], unique=False)
    op.create_index(op.f("ix_index_daily_bars_ticker"), "index_daily_bars", ["ticker"], unique=False)
    op.create_index(op.f("ix_index_daily_bars_trade_date"), "index_daily_bars", ["trade_date"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_index_daily_bars_trade_date"), table_name="index_daily_bars")
    op.drop_index(op.f("ix_index_daily_bars_ticker"), table_name="index_daily_bars")
    op.drop_index(op.f("ix_index_daily_bars_index_asset_id"), table_name="index_daily_bars")
    op.drop_index(op.f("ix_index_daily_bars_country_code"), table_name="index_daily_bars")
    op.drop_table("index_daily_bars")
