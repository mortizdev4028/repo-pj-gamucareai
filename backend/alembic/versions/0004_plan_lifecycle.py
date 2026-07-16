"""Add subscription lifecycle and renewal request details.

The migration keeps existing subscriptions intact while adding cancellation
metadata, renewal linkage and the options requested by an owner when asking for
renewal.
"""
from alembic import op
import sqlalchemy as sa

revision = '0004_plan_lifecycle'
down_revision = '0003_plan_payments'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    subscription_columns = _column_names('pet_plan_subscriptions')
    if 'cancelled_at' not in subscription_columns:
        op.add_column('pet_plan_subscriptions', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
    if 'cancellation_reason' not in subscription_columns:
        op.add_column('pet_plan_subscriptions', sa.Column('cancellation_reason', sa.Text(), nullable=True))
    if 'renewed_from_id' not in subscription_columns:
        op.add_column('pet_plan_subscriptions', sa.Column('renewed_from_id', sa.Uuid(), nullable=True))
        op.create_foreign_key(
            'fk_subscription_renewed_from',
            'pet_plan_subscriptions',
            'pet_plan_subscriptions',
            ['renewed_from_id'],
            ['id'],
        )

    renewal_columns = _column_names('renewal_requests')
    if 'requested_plan_id' not in renewal_columns:
        op.add_column('renewal_requests', sa.Column('requested_plan_id', sa.Uuid(), nullable=True))
        op.create_foreign_key(
            'fk_renewal_requested_plan',
            'renewal_requests',
            'health_plans',
            ['requested_plan_id'],
            ['id'],
        )
    if 'payment_mode' not in renewal_columns:
        op.add_column('renewal_requests', sa.Column('payment_mode', sa.String(length=20), nullable=True))
    if 'installments_total' not in renewal_columns:
        op.add_column('renewal_requests', sa.Column('installments_total', sa.Integer(), nullable=True))

    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('plan_installments'):
        op.create_table(
            'plan_installments',
            sa.Column('id', sa.Uuid(), nullable=False),
            sa.Column('subscription_id', sa.Uuid(), nullable=False),
            sa.Column('installment_number', sa.Integer(), nullable=False),
            sa.Column('due_date', sa.Date(), nullable=False),
            sa.Column('amount', sa.Numeric(8, 2), nullable=False),
            sa.Column('status', sa.String(length=30), nullable=False, server_default='pending'),
            sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(['subscription_id'], ['pet_plan_subscriptions.id']),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('subscription_id', 'installment_number', name='uq_subscription_installment'),
        )
        op.create_index('ix_plan_installments_subscription_id', 'plan_installments', ['subscription_id'])
        op.create_index('ix_plan_installments_due_date', 'plan_installments', ['due_date'])
        op.create_index('ix_plan_installments_status', 'plan_installments', ['status'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('plan_installments'):
        op.drop_index('ix_plan_installments_status', table_name='plan_installments')
        op.drop_index('ix_plan_installments_due_date', table_name='plan_installments')
        op.drop_index('ix_plan_installments_subscription_id', table_name='plan_installments')
        op.drop_table('plan_installments')

    renewal_columns = _column_names('renewal_requests')
    if 'installments_total' in renewal_columns:
        op.drop_column('renewal_requests', 'installments_total')
    if 'payment_mode' in renewal_columns:
        op.drop_column('renewal_requests', 'payment_mode')
    if 'requested_plan_id' in renewal_columns:
        op.drop_constraint('fk_renewal_requested_plan', 'renewal_requests', type_='foreignkey')
        op.drop_column('renewal_requests', 'requested_plan_id')

    subscription_columns = _column_names('pet_plan_subscriptions')
    if 'renewed_from_id' in subscription_columns:
        op.drop_constraint('fk_subscription_renewed_from', 'pet_plan_subscriptions', type_='foreignkey')
        op.drop_column('pet_plan_subscriptions', 'renewed_from_id')
    if 'cancellation_reason' in subscription_columns:
        op.drop_column('pet_plan_subscriptions', 'cancellation_reason')
    if 'cancelled_at' in subscription_columns:
        op.drop_column('pet_plan_subscriptions', 'cancelled_at')
