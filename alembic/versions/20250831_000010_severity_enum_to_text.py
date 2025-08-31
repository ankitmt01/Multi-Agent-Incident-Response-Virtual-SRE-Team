from alembic import op

# ids
revision = "20250831_000010"
down_revision = "<PUT_YOUR_LAST_REVISION_ID_HERE>"  # update this

def upgrade():
    # If the column is already text, this still succeeds on PG
    op.execute("ALTER TABLE incidents ALTER COLUMN severity TYPE VARCHAR USING severity::text;")
    # Drop enum type if present
    op.execute("""
    DO $$
    BEGIN
      IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'severity') THEN
        DROP TYPE severity;
      END IF;
    END$$;
    """)

def downgrade():
    -- no-op (we're keeping text)
    pass
