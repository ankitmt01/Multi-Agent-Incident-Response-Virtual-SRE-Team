# alembic/versions/20250831_000002_severity_enum.py
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = "20250831_000002"
down_revision = "20250831_000001"   # <= set to your previous revision id
branch_labels = None
depends_on = None

def upgrade():
    severity = postgresql.ENUM("low", "medium", "high", "critical", name="severity", create_type=True)
    severity.create(op.get_bind(), checkfirst=True)

def downgrade():
    severity = postgresql.ENUM(name="severity")
    severity.drop(op.get_bind(), checkfirst=True)
