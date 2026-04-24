"""create trading calendar days

Revision ID: 20260424_000013
Revises: 20260424_000012
Create Date: 2026-04-24 10:20:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000013"
down_revision = "20260424_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trading_calendar_days",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exchange_id", sa.Integer(), nullable=True),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchanges.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exchange_code", "trade_date", name="uq_trading_calendar_days_exchange_date"),
    )
    op.create_index(op.f("ix_trading_calendar_days_exchange_code"), "trading_calendar_days", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_trading_calendar_days_exchange_id"), "trading_calendar_days", ["exchange_id"], unique=False)
    op.create_index(op.f("ix_trading_calendar_days_trade_date"), "trading_calendar_days", ["trade_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trading_calendar_days_trade_date"), table_name="trading_calendar_days")
    op.drop_index(op.f("ix_trading_calendar_days_exchange_id"), table_name="trading_calendar_days")
    op.drop_index(op.f("ix_trading_calendar_days_exchange_code"), table_name="trading_calendar_days")
    op.drop_table("trading_calendar_days")
