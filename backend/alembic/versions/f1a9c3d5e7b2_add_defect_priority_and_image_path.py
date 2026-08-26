"""add defect priority and image path columns

Adds the two columns the pothole ML integration boundary needs on `defects`:

  * defects.defect_priority -- AHP priority score (0-100) from the existing
                                Road Intelligence service, populated only for
                                defects created via the image pipeline
                                (`POST /reports/image`)
  * defects.image_path      -- path to the uploaded source image used for
                                inference, populated only by the same path

This migration is purely additive: both columns are nullable, no existing
column changes type, nothing is dropped, and no row content is rewritten.
Defects created through the pre-existing `POST /reports` JSON endpoint are
unaffected and simply leave both columns NULL.

Revision ID: f1a9c3d5e7b2
Revises: b7c41f0d9a52
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a9c3d5e7b2'
down_revision: Union[str, Sequence[str], None] = 'b7c41f0d9a52'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'defects',
        sa.Column('defect_priority', sa.Float(), nullable=True),
    )
    op.add_column(
        'defects',
        sa.Column('image_path', sa.String(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('defects', 'image_path')
    op.drop_column('defects', 'defect_priority')
