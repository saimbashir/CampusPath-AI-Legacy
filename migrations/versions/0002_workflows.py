"""Persistent learning workflows and assessment metadata."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None
NEW=['study_plans','study_tasks','notifications','resource_blobs','teacher_assignments','viva_sessions','viva_turns']
def upgrade():
    op.add_column('users',sa.Column('active',sa.Boolean(),nullable=False,server_default=sa.true()))
    op.add_column('quiz_runs',sa.Column('settings',sa.JSON(),nullable=True))
    op.add_column('quiz_runs',sa.Column('finished',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('quiz_runs',sa.Column('hint_ids',sa.JSON(),nullable=True))
    op.add_column('quiz_runs',sa.Column('question_started',sa.DateTime(),nullable=True))
    op.add_column('answers',sa.Column('response_seconds',sa.Float(),nullable=True))
    op.add_column('answers',sa.Column('hint_used',sa.Boolean(),nullable=True))
    op.add_column('answers',sa.Column('evidence_weight',sa.Float(),nullable=True))
    with op.batch_alter_table('submissions') as batch:
        batch.add_column(sa.Column('resource_id',sa.Integer(),nullable=True))
        batch.create_foreign_key('fk_submission_resource','resources',['resource_id'],['id'])
    from migrations.schema_v2 import metadata
    metadata.create_all(op.get_bind(),tables=[metadata.tables[n] for n in NEW])
def downgrade():
    from migrations.schema_v2 import metadata
    metadata.drop_all(op.get_bind(),tables=[metadata.tables[n] for n in reversed(NEW)])
    with op.batch_alter_table('submissions') as batch:
        batch.drop_constraint('fk_submission_resource',type_='foreignkey');batch.drop_column('resource_id')
    for table,cols in [('answers',['evidence_weight','hint_used','response_seconds']),('quiz_runs',['question_started','hint_ids','finished','settings']),('users',['active'])]:
        with op.batch_alter_table(table) as batch:
            for name in cols:batch.drop_column(name)
