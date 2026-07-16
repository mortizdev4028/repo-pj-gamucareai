"""Add plan payment tracking to subscriptions.

Existing subscriptions are marked as fully paid using the one-off plan price.
New demo subscriptions can use either full payment or up to twelve instalments.
"""
from alembic import op
import sqlalchemy as sa

revision = '0003_plan_payments'
down_revision = '0002_roles_and_soft_delete'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    columns = _column_names('pet_plan_subscriptions')
    if 'payment_mode' not in columns:
        op.add_column(
            'pet_plan_subscriptions',
            sa.Column('payment_mode', sa.String(length=20), nullable=False, server_default='single'),
        )
    if 'installments_total' not in columns:
        op.add_column(
            'pet_plan_subscriptions',
            sa.Column('installments_total', sa.Integer(), nullable=False, server_default='1'),
        )
    if 'installments_paid' not in columns:
        op.add_column(
            'pet_plan_subscriptions',
            sa.Column('installments_paid', sa.Integer(), nullable=False, server_default='1'),
        )
    if 'total_amount' not in columns:
        op.add_column(
            'pet_plan_subscriptions',
            sa.Column('total_amount', sa.Numeric(8, 2), nullable=True),
        )
        op.execute("""
            UPDATE pet_plan_subscriptions AS subscription
            SET total_amount = plan.price_single
            FROM health_plans AS plan
            WHERE plan.id = subscription.health_plan_id
        """)
        op.alter_column('pet_plan_subscriptions', 'total_amount', nullable=False)


def downgrade() -> None:
    columns = _column_names('pet_plan_subscriptions')
    for column in ('total_amount', 'installments_paid', 'installments_total', 'payment_mode'):
        if column in columns:
            op.drop_column('pet_plan_subscriptions', column)
