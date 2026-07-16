"""Add auditable Wakyma mock import batches and record details."""
from alembic import op
import sqlalchemy as sa

revision = '0007_wakyma_integration'
down_revision = '0006_rag_quality'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = _column_names('import_batches')
    additions = [
        ('requested_by_id', sa.Column('requested_by_id', sa.Uuid(), nullable=True)),
        ('file_format', sa.Column('file_format', sa.String(length=20), nullable=False, server_default='json')),
        ('schema_version', sa.Column('schema_version', sa.String(length=20), nullable=False, server_default='1.0')),
        ('checksum', sa.Column('checksum', sa.String(length=64), nullable=True)),
        ('dry_run', sa.Column('dry_run', sa.Boolean(), nullable=False, server_default=sa.false())),
        ('records_total', sa.Column('records_total', sa.Integer(), nullable=False, server_default='0')),
        ('records_created', sa.Column('records_created', sa.Integer(), nullable=False, server_default='0')),
        ('records_updated', sa.Column('records_updated', sa.Integer(), nullable=False, server_default='0')),
        ('records_skipped', sa.Column('records_skipped', sa.Integer(), nullable=False, server_default='0')),
        ('summary', sa.Column('summary', sa.JSON(), nullable=True)),
    ]
    for name, column in additions:
        if name not in columns:
            op.add_column('import_batches', column)

    foreign_keys = {fk.get('name') for fk in inspector.get_foreign_keys('import_batches')}
    if 'fk_import_batches_requested_by' not in foreign_keys:
        op.create_foreign_key(
            'fk_import_batches_requested_by',
            'import_batches',
            'users',
            ['requested_by_id'],
            ['id'],
        )

    indexes = {item['name'] for item in inspector.get_indexes('import_batches')}
    if 'ix_import_batches_started_at' not in indexes:
        op.create_index('ix_import_batches_started_at', 'import_batches', ['started_at'])
    if 'ix_import_batches_status' not in indexes:
        op.create_index('ix_import_batches_status', 'import_batches', ['status'])

    if not inspector.has_table('import_batch_items'):
        op.create_table(
            'import_batch_items',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('batch_id', sa.Uuid(), nullable=False),
            sa.Column('row_number', sa.Integer(), nullable=False),
            sa.Column('entity_type', sa.String(length=30), nullable=False),
            sa.Column('external_id', sa.String(length=120), nullable=True),
            sa.Column('action', sa.String(length=30), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False),
            sa.Column('message', sa.Text(), nullable=True),
            sa.Column('payload', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['batch_id'], ['import_batches.id'], name='fk_import_batch_items_batch', ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_import_batch_items_batch_id', 'import_batch_items', ['batch_id'])
        op.create_index('ix_import_batch_items_status', 'import_batch_items', ['status'])
        op.create_index('ix_import_batch_items_entity_type', 'import_batch_items', ['entity_type'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('import_batch_items'):
        op.drop_index('ix_import_batch_items_entity_type', table_name='import_batch_items')
        op.drop_index('ix_import_batch_items_status', table_name='import_batch_items')
        op.drop_index('ix_import_batch_items_batch_id', table_name='import_batch_items')
        op.drop_table('import_batch_items')

    indexes = {item['name'] for item in inspector.get_indexes('import_batches')}
    for index_name in ('ix_import_batches_status', 'ix_import_batches_started_at'):
        if index_name in indexes:
            op.drop_index(index_name, table_name='import_batches')

    foreign_keys = {fk.get('name') for fk in inspector.get_foreign_keys('import_batches')}
    if 'fk_import_batches_requested_by' in foreign_keys:
        op.drop_constraint('fk_import_batches_requested_by', 'import_batches', type_='foreignkey')

    columns = _column_names('import_batches')
    for name in (
        'summary', 'records_skipped', 'records_updated', 'records_created', 'records_total',
        'dry_run', 'checksum', 'schema_version', 'file_format', 'requested_by_id',
    ):
        if name in columns:
            op.drop_column('import_batches', name)
