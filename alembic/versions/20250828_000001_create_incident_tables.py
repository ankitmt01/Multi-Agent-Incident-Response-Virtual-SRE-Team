from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20250831_000001"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "incidents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("service", sa.String(length=200), nullable=False),
        sa.Column("severity", sa.Enum("low","medium","high","critical", name="severity"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("suspected_cause", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
    )

    op.create_table(
        "incident_signals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.String(length=64), sa.ForeignKey("incidents.id", ondelete="CASCADE")),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(length=32)),
        sa.Column("window_s", sa.Integer),
        sa.Column("at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_signal_incident", "incident_signals", ["incident_id"])

    jsonb = postgresql.JSONB
    # fallback to JSON when not Postgres will be handled by SQLAlchemy at runtime

    op.create_table(
        "incident_evidence",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.String(length=64), sa.ForeignKey("incidents.id", ondelete="CASCADE")),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0"),
        sa.Column("uri", sa.String(length=500)),
    )
    op.create_index("ix_evidence_incident", "incident_evidence", ["incident_id"])

    op.create_table(
        "remediation_candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.String(length=64), sa.ForeignKey("incidents.id", ondelete="CASCADE")),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("steps", jsonb, nullable=False, server_default="[]"),
        sa.Column("risks", jsonb, nullable=False, server_default="[]"),
        sa.Column("rollback", jsonb, nullable=False, server_default="[]"),
        sa.Column("rationale", sa.Text, nullable=False, server_default=""),
        sa.Column("predicted_impact", jsonb, nullable=False, server_default="{}"),
        sa.Column("actions", jsonb, nullable=False, server_default="[]"),
        sa.Column("policy_status", sa.String(length=32), nullable=False, server_default="unknown"),
        sa.Column("policy_reasons", jsonb, nullable=False, server_default="[]"),
    )
    op.create_index("ix_candidates_incident", "remediation_candidates", ["incident_id"])

    op.create_table(
        "validation_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("incident_id", sa.String(length=64), sa.ForeignKey("incidents.id", ondelete="CASCADE")),
        sa.Column("candidate", sa.String(length=200), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("kpi_before", jsonb, nullable=False, server_default="{}"),
        sa.Column("kpi_after", jsonb, nullable=False, server_default="{}"),
    )
    op.create_index("ix_validations_incident", "validation_results", ["incident_id"])


def downgrade():
    op.drop_index("ix_validations_incident", table_name="validation_results")
    op.drop_table("validation_results")
    op.drop_index("ix_candidates_incident", table_name="remediation_candidates")
    op.drop_table("remediation_candidates")
    op.drop_index("ix_evidence_incident", table_name="incident_evidence")
    op.drop_table("incident_evidence")
    op.drop_index("ix_signal_incident", table_name="incident_signals")
    op.drop_table("incident_signals")
    op.drop_table("incidents")
    sa.Enum(name="severity").drop(op.get_bind(), checkfirst=False)
