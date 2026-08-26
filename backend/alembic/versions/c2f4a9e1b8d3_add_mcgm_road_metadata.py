"""add MCGM demo road metadata columns

Adds the source metadata columns the MCGM demo road importer
(backend/scripts/import_demo_roads.py) needs on `road_segments`:

  * road_segments.mcgm_id         -- the MCGM CSV's own `id`, the stable
                                      external key the importer upserts on
  * road_segments.ward            -- MCGM ward (e.g. "H/W")
  * road_segments.work_status     -- MCGM's own road-work status string
                                      (e.g. "Work In Progress"). NOT
                                      Defect.defect_status -- never feeds
                                      Road Health scoring.
  * road_segments.source_length_m -- the CSV's own length_of_road_m,
                                      preserved as metadata alongside the
                                      geometry-derived length_km

This migration is purely additive: no tables created, nothing dropped, no
column type changed, no row content rewritten. All four columns are
nullable, so every existing `dev_approximate_v1`/`osm_overpass` segment is
unaffected and simply leaves them NULL.

Revision ID: c2f4a9e1b8d3
Revises: e24e300086b5
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f4a9e1b8d3'
down_revision: Union[str, Sequence[str], None] = 'e24e300086b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'road_segments',
        sa.Column('mcgm_id', sa.String(length=50), nullable=True),
    )
    op.create_index(
        op.f('ix_road_segments_mcgm_id'), 'road_segments', ['mcgm_id'],
    )
    op.add_column(
        'road_segments',
        sa.Column('ward', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'road_segments',
        sa.Column('work_status', sa.String(length=100), nullable=True),
    )
    op.add_column(
        'road_segments',
        sa.Column('source_length_m', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('road_segments', 'source_length_m')
    op.drop_column('road_segments', 'work_status')
    op.drop_column('road_segments', 'ward')
    op.drop_index(op.f('ix_road_segments_mcgm_id'), table_name='road_segments')
    op.drop_column('road_segments', 'mcgm_id')
