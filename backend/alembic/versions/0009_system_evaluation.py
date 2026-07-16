"""Store formal MVP quality and evaluation reports."""
from alembic import op
import sqlalchemy as sa

revision = '0009_system_evaluation'
down_revision = '0008_security_audit'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('system_evaluation_runs'):
        return
    op.create_table(
        'system_evaluation_runs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('app_version', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='running'),
        sa.Column('suite_name', sa.String(length=120), nullable=False, server_default='mvp_quality_v1'),
        sa.Column('tests_total', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tests_passed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('tests_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('coverage_percent', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('metrics', sa.JSON(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('report_markdown', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_system_evaluation_runs_app_version', 'system_evaluation_runs', ['app_version'])
    op.create_index('ix_system_evaluation_runs_status', 'system_evaluation_runs', ['status'])
    op.create_index('ix_system_evaluation_runs_started_at', 'system_evaluation_runs', ['started_at'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('system_evaluation_runs'):
        return
    indexes = {item['name'] for item in inspector.get_indexes('system_evaluation_runs')}
    for name in (
        'ix_system_evaluation_runs_started_at',
        'ix_system_evaluation_runs_status',
        'ix_system_evaluation_runs_app_version',
    ):
        if name in indexes:
            op.drop_index(name, table_name='system_evaluation_runs')
    op.drop_table('system_evaluation_runs')
