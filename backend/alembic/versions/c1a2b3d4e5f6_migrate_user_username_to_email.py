"""migrate user username to email

Revision ID: c1a2b3d4e5f6
Revises: acea8cf29071
Create Date: 2026-06-06 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1a2b3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "acea8cf29071"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Rename the username column to email and update constraints."""
    # Rename the column
    op.alter_column(
        "users",
        "username",
        new_column_name="email",
        existing_type=sa.String(255),
        existing_nullable=False,
    )
    # PostgreSQL auto-names the unique constraint as 'users_username_key'
    # when created with sa.UniqueConstraint("username") without an explicit name.
    op.drop_constraint("users_username_key", "users", type_="unique")
    # Create a unique index on the new email column
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    """Revert email column back to username."""
    op.drop_index("ix_users_email", table_name="users")
    op.create_unique_constraint("users_username_key", "users", ["username"])
    op.alter_column(
        "users",
        "email",
        new_column_name="username",
        existing_type=sa.String(255),
        existing_nullable=False,
    )
