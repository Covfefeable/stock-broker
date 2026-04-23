"""create stocks

Revision ID: 20260424_000005
Revises: 20260424_000004
Create Date: 2026-04-24 00:00:05

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000005"
down_revision = "20260424_000004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
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
        sa.UniqueConstraint("exchange_code", "ticker", name="uq_stocks_exchange_ticker"),
    )
    op.create_index(op.f("ix_stocks_country_code"), "stocks", ["country_code"], unique=False)
    op.create_index(op.f("ix_stocks_country_id"), "stocks", ["country_id"], unique=False)
    op.create_index(op.f("ix_stocks_exchange_code"), "stocks", ["exchange_code"], unique=False)
    op.create_index(op.f("ix_stocks_exchange_id"), "stocks", ["exchange_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_stocks_exchange_id"), table_name="stocks")
    op.drop_index(op.f("ix_stocks_exchange_code"), table_name="stocks")
    op.drop_index(op.f("ix_stocks_country_id"), table_name="stocks")
    op.drop_index(op.f("ix_stocks_country_code"), table_name="stocks")
    op.drop_table("stocks")
