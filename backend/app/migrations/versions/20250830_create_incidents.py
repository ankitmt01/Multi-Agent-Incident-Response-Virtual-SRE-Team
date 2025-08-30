"""create incidents table

Revision ID: 20250830_create_incidents
Revises:
Create Date: 2025-08-30 00:00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

# revision identifiers, used by Alembic.
revision = "20250830_create_incidents"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("service", sa.String(length=128), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("suspected_cause", sa.Text(), nullable=True),
        sa.Column("signals", pg.JSONB, nullable=False),
        sa.Column("evidence", pg.JSONB, nullable=False),
        sa.Column("remediation_candidates", pg.JSONB, nullable=False),
        sa.Column("validation_results", pg.JSONB, nullable=False),
    )
    op.create_index(
        "ix_incidents_service_created",
        "incidents",
        ["service", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_incidents_status_created",
        "incidents",
        ["status", "created_at"],
        unique=False,
    )

def downgrade() -> None:
    op.drop_index("ix_incidents_status_created", table_name="incidents")
    op.drop_index("ix_incidents_service_created", table_name="incidents")
    op.drop_table("incidents")
