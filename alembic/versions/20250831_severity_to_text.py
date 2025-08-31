from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20250831_severity_to_text"
down_revision = "<PUT_PREVIOUS_REVISION_HERE>"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.alter_column(
        "incidents",
        "severity",
        type_=sa.String(length=16),
        existing_nullable=True,
        postgresql_using="severity::text",
    )
    # drop enum type if it exists (best-effort)
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_type WHERE typname='severity') THEN
        DROP TYPE severity;
      END IF;
    END$$;
    """)

def downgrade() -> None:
    # optional: recreate enum if you really want to
    pass
