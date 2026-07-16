"""Add RAG document governance and evaluation run storage."""
from alembic import op
import sqlalchemy as sa

revision = '0006_rag_quality'
down_revision = '0005_preventive_alerts'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names('rag_documents')
    additions = [
        ('language', sa.Column('language', sa.String(length=10), nullable=False, server_default='es')),
        ('audience', sa.Column('audience', sa.String(length=30), nullable=False, server_default='owner')),
        ('source_type', sa.Column('source_type', sa.String(length=40), nullable=False, server_default='guideline')),
        ('trust_level', sa.Column('trust_level', sa.String(length=30), nullable=False, server_default='official')),
        ('tags', sa.Column('tags', sa.JSON(), nullable=False, server_default='[]')),
        ('last_reviewed_at', sa.Column('last_reviewed_at', sa.Date(), nullable=True)),
    ]
    for name, column in additions:
        if name not in columns:
            op.add_column('rag_documents', column)

    indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes('rag_documents')}
    if 'ix_rag_documents_trust_level' not in indexes:
        op.create_index('ix_rag_documents_trust_level', 'rag_documents', ['trust_level'])

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('rag_evaluation_runs'):
        op.create_table(
            'rag_evaluation_runs',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('mode', sa.String(length=30), nullable=False, server_default='retrieval'),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='running'),
            sa.Column('dataset_name', sa.String(length=120), nullable=False, server_default='rag_cases_v1'),
            sa.Column('cases_total', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('metrics', sa.JSON(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('model_name', sa.String(length=120), nullable=True),
            sa.Column('error', sa.Text(), nullable=True),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_rag_evaluation_runs_status', 'rag_evaluation_runs', ['status'])
        op.create_index('ix_rag_evaluation_runs_started_at', 'rag_evaluation_runs', ['started_at'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('rag_evaluation_runs'):
        op.drop_index('ix_rag_evaluation_runs_started_at', table_name='rag_evaluation_runs')
        op.drop_index('ix_rag_evaluation_runs_status', table_name='rag_evaluation_runs')
        op.drop_table('rag_evaluation_runs')

    indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes('rag_documents')}
    if 'ix_rag_documents_trust_level' in indexes:
        op.drop_index('ix_rag_documents_trust_level', table_name='rag_documents')
    columns = _column_names('rag_documents')
    for name in ('last_reviewed_at', 'tags', 'trust_level', 'source_type', 'audience', 'language'):
        if name in columns:
            op.drop_column('rag_documents', name)
