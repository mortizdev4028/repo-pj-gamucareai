"""Version preventive rules and add a complete alert lifecycle."""
from alembic import op
import sqlalchemy as sa

revision = '0005_preventive_alerts'
down_revision = '0004_plan_lifecycle'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    rule_columns = _column_names('risk_rules')
    additions = [
        ('description', sa.Column('description', sa.Text(), nullable=True)),
        ('category', sa.Column('category', sa.String(length=80), nullable=False, server_default='general')),
        ('source_url', sa.Column('source_url', sa.Text(), nullable=True)),
        ('source_date', sa.Column('source_date', sa.Date(), nullable=True)),
        ('reviewed_at', sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True)),
        ('auto_resolve', sa.Column('auto_resolve', sa.Boolean(), nullable=False, server_default=sa.true())),
        ('version', sa.Column('version', sa.Integer(), nullable=False, server_default='1')),
    ]
    for name, column in additions:
        if name not in rule_columns:
            op.add_column('risk_rules', column)
    inspector = sa.inspect(op.get_bind())
    rule_indexes = {index['name'] for index in inspector.get_indexes('risk_rules')}
    if 'ix_risk_rules_category' not in rule_indexes:
        op.create_index('ix_risk_rules_category', 'risk_rules', ['category'])

    alert_columns = _column_names('risk_alerts')
    alert_additions = [
        ('updated_at', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())),
        ('last_evaluated_at', sa.Column('last_evaluated_at', sa.DateTime(timezone=True), nullable=True)),
        ('occurrence_count', sa.Column('occurrence_count', sa.Integer(), nullable=False, server_default='1')),
        ('reviewed_by_id', sa.Column('reviewed_by_id', sa.Uuid(), nullable=True)),
        ('review_notes', sa.Column('review_notes', sa.Text(), nullable=True)),
        ('resolved_at', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True)),
        ('dismissed_at', sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True)),
        ('resolution_reason', sa.Column('resolution_reason', sa.Text(), nullable=True)),
    ]
    for name, column in alert_additions:
        if name not in alert_columns:
            op.add_column('risk_alerts', column)
    if 'reviewed_by_id' not in alert_columns:
        op.create_foreign_key(
            'fk_risk_alert_reviewed_by',
            'risk_alerts',
            'users',
            ['reviewed_by_id'],
            ['id'],
        )

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('alert_status_history'):
        op.create_table(
            'alert_status_history',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('alert_id', sa.Uuid(), nullable=False),
            sa.Column('from_status', sa.String(length=30), nullable=True),
            sa.Column('to_status', sa.String(length=30), nullable=False),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('changed_by_id', sa.Uuid(), nullable=True),
            sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['alert_id'], ['risk_alerts.id']),
            sa.ForeignKeyConstraint(['changed_by_id'], ['users.id']),
            sa.PrimaryKeyConstraint('id'),
        )
        op.create_index('ix_alert_status_history_alert_id', 'alert_status_history', ['alert_id'])
        op.create_index('ix_alert_status_history_to_status', 'alert_status_history', ['to_status'])
        op.create_index('ix_alert_status_history_changed_at', 'alert_status_history', ['changed_at'])

    # Preserve the existing generated timestamp as the first known update.
    op.execute('UPDATE risk_alerts SET updated_at = generated_at WHERE updated_at IS NULL')


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('alert_status_history'):
        op.drop_index('ix_alert_status_history_changed_at', table_name='alert_status_history')
        op.drop_index('ix_alert_status_history_to_status', table_name='alert_status_history')
        op.drop_index('ix_alert_status_history_alert_id', table_name='alert_status_history')
        op.drop_table('alert_status_history')

    alert_columns = _column_names('risk_alerts')
    if 'reviewed_by_id' in alert_columns:
        op.drop_constraint('fk_risk_alert_reviewed_by', 'risk_alerts', type_='foreignkey')
    for name in ['resolution_reason', 'dismissed_at', 'resolved_at', 'review_notes', 'reviewed_by_id',
                 'occurrence_count', 'last_evaluated_at', 'updated_at']:
        if name in _column_names('risk_alerts'):
            op.drop_column('risk_alerts', name)

    inspector = sa.inspect(op.get_bind())
    rule_indexes = {index['name'] for index in inspector.get_indexes('risk_rules')}
    if 'ix_risk_rules_category' in rule_indexes:
        op.drop_index('ix_risk_rules_category', table_name='risk_rules')
    for name in ['version', 'auto_resolve', 'reviewed_at', 'source_date', 'source_url', 'category', 'description']:
        if name in _column_names('risk_rules'):
            op.drop_column('risk_rules', name)
