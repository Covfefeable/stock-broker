"""create exchanges

Revision ID: 20260424_000004
Revises: 20260424_000003
Create Date: 2026-04-24 00:00:04

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000004"
down_revision = "20260424_000003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exchanges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exchange_code", sa.String(length=16), nullable=False),
        sa.Column("exchange_name", sa.String(length=160), nullable=False),
        sa.Column("exchange_name_short", sa.String(length=80), nullable=True),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("currency_code", sa.String(length=8), nullable=True),
        sa.Column("local_open", sa.String(length=16), nullable=True),
        sa.Column("local_close", sa.String(length=16), nullable=True),
        sa.Column("beijing_open", sa.String(length=16), nullable=True),
        sa.Column("beijing_close", sa.String(length=16), nullable=True),
        sa.Column("timezone", sa.String(length=120), nullable=True),
        sa.Column("delay", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_exchanges_country_code"), "exchanges", ["country_code"], unique=False)
    op.create_index(op.f("ix_exchanges_country_id"), "exchanges", ["country_id"], unique=False)
    op.create_index(op.f("ix_exchanges_exchange_code"), "exchanges", ["exchange_code"], unique=True)


def downgrade():
    op.drop_index(op.f("ix_exchanges_exchange_code"), table_name="exchanges")
    op.drop_index(op.f("ix_exchanges_country_id"), table_name="exchanges")
    op.drop_index(op.f("ix_exchanges_country_code"), table_name="exchanges")
    op.drop_table("exchanges")
