"""Initial schema; metadata snapshot generated for this release."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    from migrations.schema_v1 import metadata
    metadata.create_all(op.get_bind())
def downgrade():
    from migrations.schema_v1 import metadata
    metadata.drop_all(op.get_bind())
