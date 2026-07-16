"""Add session security, account lockout and immutable audit records."""
from alembic import op
import sqlalchemy as sa

revision = '0008_security_audit'
down_revision = '0007_wakyma_integration'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = _column_names('users')
    additions = [
        ('must_change_password', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false())),
        ('failed_login_attempts', sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0')),
        ('locked_until', sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True)),
        ('password_changed_at', sa.Column('password_changed_at', sa.DateTime(timezone=True), nullable=True)),
        ('token_version', sa.Column('token_version', sa.Integer(), nullable=False, server_default='1')),
    ]
    for name, column in additions:
        if name not in columns:
            op.add_column('users', column)

    if not inspector.has_table('refresh_sessions'):
        op.create_table(
            'refresh_sessions',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('user_id', sa.Uuid(), nullable=False),
            sa.Column('token_hash', sa.String(length=64), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('ip_address', sa.String(length=64), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_refresh_sessions_user', ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('token_hash', name='uq_refresh_sessions_token_hash'),
        )
        op.create_index('ix_refresh_sessions_user_id', 'refresh_sessions', ['user_id'])
        op.create_index('ix_refresh_sessions_token_hash', 'refresh_sessions', ['token_hash'], unique=True)
        op.create_index('ix_refresh_sessions_created_at', 'refresh_sessions', ['created_at'])
        op.create_index('ix_refresh_sessions_expires_at', 'refresh_sessions', ['expires_at'])
        op.create_index('ix_refresh_sessions_revoked_at', 'refresh_sessions', ['revoked_at'])

    if not inspector.has_table('audit_logs'):
        op.create_table(
            'audit_logs',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('actor_user_id', sa.Uuid(), nullable=True),
            sa.Column('actor_email', sa.String(length=255), nullable=True),
            sa.Column('action', sa.String(length=80), nullable=False),
            sa.Column('entity_type', sa.String(length=80), nullable=False),
            sa.Column('entity_id', sa.String(length=120), nullable=True),
            sa.Column('outcome', sa.String(length=30), nullable=False, server_default='success'),
            sa.Column('request_id', sa.String(length=80), nullable=True),
            sa.Column('ip_address', sa.String(length=64), nullable=True),
            sa.Column('user_agent', sa.String(length=255), nullable=True),
            sa.Column('before_values', sa.JSON(), nullable=True),
            sa.Column('after_values', sa.JSON(), nullable=True),
            sa.Column('details', sa.JSON(), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(['actor_user_id'], ['users.id'], name='fk_audit_logs_actor', ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
        )
        for column in ('actor_user_id', 'actor_email', 'action', 'entity_type', 'entity_id', 'outcome', 'request_id', 'created_at'):
            op.create_index(f'ix_audit_logs_{column}', 'audit_logs', [column])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('audit_logs'):
        for column in ('created_at', 'request_id', 'outcome', 'entity_id', 'entity_type', 'action', 'actor_email', 'actor_user_id'):
            name = f'ix_audit_logs_{column}'
            indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes('audit_logs')}
            if name in indexes:
                op.drop_index(name, table_name='audit_logs')
        op.drop_table('audit_logs')
    if inspector.has_table('refresh_sessions'):
        indexes = {item['name'] for item in sa.inspect(op.get_bind()).get_indexes('refresh_sessions')}
        for name in ('ix_refresh_sessions_revoked_at', 'ix_refresh_sessions_expires_at', 'ix_refresh_sessions_created_at', 'ix_refresh_sessions_token_hash', 'ix_refresh_sessions_user_id'):
            if name in indexes:
                op.drop_index(name, table_name='refresh_sessions')
        op.drop_table('refresh_sessions')
    columns = _column_names('users')
    for name in ('token_version', 'password_changed_at', 'locked_until', 'failed_login_attempts', 'must_change_password'):
        if name in columns:
            op.drop_column('users', name)
