"""create index assets

Revision ID: 20260424_000006
Revises: 20260424_000005
Create Date: 2026-04-24 00:00:06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000006"
down_revision = "20260424_000005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "index_assets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("country_id", sa.Integer(), nullable=True),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["country_id"], ["countries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("country_code", "ticker", name="uq_index_assets_country_ticker"),
    )
    op.create_index(op.f("ix_index_assets_country_code"), "index_assets", ["country_code"], unique=False)
    op.create_index(op.f("ix_index_assets_country_id"), "index_assets", ["country_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_index_assets_country_id"), table_name="index_assets")
    op.drop_index(op.f("ix_index_assets_country_code"), table_name="index_assets")
    op.drop_table("index_assets")
