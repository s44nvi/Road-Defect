"""add road health metadata columns

Adds the three columns the Road Health feature needs on top of the existing
road-health foundation (revision edd5ed491120):

  * road_segments.segment_label   -- human-friendly segment name
  * road_segments.geometry_source -- provenance of the stored geometry
  * defects.is_test_data          -- separates seeded dev data from real
                                     citizen reports

This migration is purely additive. It creates no tables, drops nothing,
changes no column type, and rewrites no row content. `defects.is_test_data`
carries a server-side DEFAULT of false so existing defect rows are backfilled
by PostgreSQL itself.

Revision ID: b7c41f0d9a52
Revises: edd5ed491120
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7c41f0d9a52'
down_revision: Union[str, Sequence[str], None] = 'edd5ed491120'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'road_segments',
        sa.Column('segment_label', sa.String(length=255), nullable=True),
    )
    op.add_column(
        'road_segments',
        sa.Column('geometry_source', sa.String(length=100), nullable=True),
    )
    op.add_column(
        'defects',
        sa.Column(
            'is_test_data',
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('defects', 'is_test_data')
    op.drop_column('road_segments', 'geometry_source')
    op.drop_column('road_segments', 'segment_label')
