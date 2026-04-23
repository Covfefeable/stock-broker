"""create countries and event logs

Revision ID: 20260424_000003
Revises: 20260424_000002
Create Date: 2026-04-24 00:00:03

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260424_000003"
down_revision = "20260424_000002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=False),
        sa.Column("country_name", sa.String(length=120), nullable=False),
        sa.Column("timezone", sa.String(length=120), nullable=True),
        sa.Column("delay", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_countries_country_code"), "countries", ["country_code"], unique=True)

    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("target", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("level", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("records_affected", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_logs_event_type"), "event_logs", ["event_type"], unique=False)
    op.create_index(op.f("ix_event_logs_status"), "event_logs", ["status"], unique=False)
    op.create_index(op.f("ix_event_logs_user_id"), "event_logs", ["user_id"], unique=False)


def downgrade():
    op.drop_index(op.f("ix_event_logs_user_id"), table_name="event_logs")
    op.drop_index(op.f("ix_event_logs_status"), table_name="event_logs")
    op.drop_index(op.f("ix_event_logs_event_type"), table_name="event_logs")
    op.drop_table("event_logs")
    op.drop_index(op.f("ix_countries_country_code"), table_name="countries")
    op.drop_table("countries")
