"""Reduce the application roles and add reversible deactivation.

The first project migration creates tables from the current SQLAlchemy metadata.
For that reason this revision checks the live schema before adding columns, so
it works both when upgrading an existing v0.1 database and when creating a new
installation from scratch.
"""
from alembic import op
import sqlalchemy as sa

revision = '0002_roles_and_soft_delete'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def _column_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column['name'] for column in inspector.get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {index['name'] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if 'is_active' not in _column_names('owners'):
        op.add_column('owners', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    if 'ix_owners_is_active' not in _index_names('owners'):
        op.create_index('ix_owners_is_active', 'owners', ['is_active'], unique=False)

    if 'is_active' not in _column_names('pets'):
        op.add_column('pets', sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    if 'ix_pets_is_active' not in _index_names('pets'):
        op.create_index('ix_pets_is_active', 'pets', ['is_active'], unique=False)

    # The former administrator and clinic roles become the profile with write
    # permissions. The former veterinarian account becomes read-only staff.
    op.execute("UPDATE users SET role = 'clinic' WHERE role IN ('admin', 'clinic')")
    op.execute("UPDATE users SET role = 'staff' WHERE role = 'vet'")
    op.execute("""
        UPDATE users
        SET email = 'staff@gamucare.local'
        WHERE email = 'vet@gamucare.local'
          AND NOT EXISTS (
              SELECT 1 FROM users WHERE email = 'staff@gamucare.local'
          )
    """)


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'vet' WHERE role = 'staff'")
    if 'ix_pets_is_active' in _index_names('pets'):
        op.drop_index('ix_pets_is_active', table_name='pets')
    if 'is_active' in _column_names('pets'):
        op.drop_column('pets', 'is_active')
    if 'ix_owners_is_active' in _index_names('owners'):
        op.drop_index('ix_owners_is_active', table_name='owners')
    if 'is_active' in _column_names('owners'):
        op.drop_column('owners', 'is_active')
