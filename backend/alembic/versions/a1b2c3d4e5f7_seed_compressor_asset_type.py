"""seed compressor asset type

Revision ID: a1b2c3d4e5f7
Revises: f1g2h3i4j5k6
Create Date: 2026-06-25 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f7"
down_revision: Union[str, Sequence[str], None] = "f1g2h3i4j5k6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Ensure an asset_types row named exactly 'compressor' exists.

    The ML training pipeline (scripts/training/run_training.py) looks
    up asset types by exact name match (case-insensitive). Development
    databases had a placeholder row named 'test_compressor' instead —
    discovered when the first real end-to-end training run failed at
    registrar.py's asset_type lookup with a clean "not found" error.

    Idempotent and order-independent:
        - If a row named 'test_compressor' exists, rename it.
        - Otherwise, insert a fresh 'compressor' row.
        - If a row already named 'compressor' exists, do nothing.
    This makes the migration safe to run against a dev database with
    the placeholder data, or against a fresh database with neither row.
    """
    connection = op.get_bind()

    existing_compressor = connection.execute(
        sa.text("SELECT id FROM asset_types WHERE name = 'compressor'")
    ).first()
    if existing_compressor is not None:
        return

    test_placeholder = connection.execute(
        sa.text("SELECT id FROM asset_types WHERE name = 'test_compressor'")
    ).first()

    if test_placeholder is not None:
        connection.execute(
            sa.text(
                "UPDATE asset_types SET name = 'compressor' "
                "WHERE id = :id"
            ),
            {"id": test_placeholder[0]},
        )
    else:
        connection.execute(
            sa.text(
                "INSERT INTO asset_types (name, description) "
                "VALUES ('compressor', 'Industrial compressor')"
            )
        )


def downgrade() -> None:
    """
    Revert the 'compressor' row.

    Mirrors upgrade(): if no asset currently references this row,
    it's safe to either rename it back to 'test_compressor' or delete
    it, depending on whether it looks like a fresh insert or a rename.
    We can't distinguish those two cases after the fact, so downgrade
    renames back to 'test_compressor' rather than deleting — matching
    the dev-database state this migration was written against, and
    avoiding an unnecessary delete if any asset has since been
    assigned to this row.
    """
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE asset_types SET name = 'test_compressor' "
            "WHERE name = 'compressor'"
        )
    )