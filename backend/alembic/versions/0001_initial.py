"""Create the initial GamuCare schema.

The first migration intentionally creates the tables from SQLAlchemy metadata.
Subsequent schema changes should use explicit Alembic operations generated with
`alembic revision --autogenerate`.
"""
from alembic import op

from app.database import Base
from app import models  # noqa: F401

revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
