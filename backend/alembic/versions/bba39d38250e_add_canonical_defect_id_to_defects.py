"""add canonical_defect_id to defects

Revision ID: bba39d38250e
Revises: 7bc6838e6493
Create Date: 2026-08-27 13:05:59.369241

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bba39d38250e'
down_revision: Union[str, Sequence[str], None] = '7bc6838e6493'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Adds a nullable self-referential `canonical_defect_id` column on
    `defects` for duplicate-report consolidation (see `app/consolidation.py`).
    Deliberately scoped to only this column/index/FK -- unrelated index
    drift on `encroachments`/`manholes` detected by autogenerate (MCGM
    data-layer tables, pre-existing before this change) is intentionally
    left out of this migration.
    """
    op.add_column('defects', sa.Column('canonical_defect_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_defects_canonical_defect_id'), 'defects', ['canonical_defect_id'], unique=False)
    op.create_foreign_key('fk_defects_canonical_defect_id_defects', 'defects', 'defects', ['canonical_defect_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_defects_canonical_defect_id_defects', 'defects', type_='foreignkey')
    op.drop_index(op.f('ix_defects_canonical_defect_id'), table_name='defects')
    op.drop_column('defects', 'canonical_defect_id')
