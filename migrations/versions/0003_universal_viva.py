"""Subject independent structure and material-grounded formal viva."""
from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'
branch_labels=None
depends_on=None
NEW=['viva_exams','viva_questions','oral_sessions','oral_responses','oral_reviews']
def upgrade():
    op.add_column('courses',sa.Column('material_only',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('assignments',sa.Column('source_ids',sa.JSON(),nullable=True))
    op.add_column('questions',sa.Column('source_ids',sa.JSON(),nullable=True))
    for table in ['chunks','topics']:op.add_column(table,sa.Column('structure',sa.JSON(),nullable=True))
    from migrations.schema_v3 import metadata
    metadata.create_all(op.get_bind(),tables=[metadata.tables[n] for n in NEW])
def downgrade():
    from migrations.schema_v3 import metadata
    metadata.drop_all(op.get_bind(),tables=[metadata.tables[n] for n in reversed(NEW)])
    with op.batch_alter_table('assignments') as b:b.drop_column('source_ids')
    with op.batch_alter_table('questions') as b:b.drop_column('source_ids')
    for table in ['chunks','topics']:
        with op.batch_alter_table(table) as b:b.drop_column('structure')
    with op.batch_alter_table('courses') as b:b.drop_column('material_only')
