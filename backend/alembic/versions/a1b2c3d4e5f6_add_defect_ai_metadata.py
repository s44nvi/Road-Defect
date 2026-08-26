"""add defect ai metadata

Adds nullable AI-detection metadata columns to `defects`, populated by the
new analyze/submit pipeline (POST /reports/analyze + POST /reports/submit):
ai_confidence, ai_bbox, ai_severity_score, ai_model_source.

All nullable -- existing rows and defects created through routes that don't
run AI detection (POST /reports, legacy seed data) remain valid.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "e24e300086b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("defects", sa.Column("ai_confidence", sa.Float(), nullable=True))
    op.add_column("defects", sa.Column("ai_bbox", sa.JSON(), nullable=True))
    op.add_column("defects", sa.Column("ai_severity_score", sa.Float(), nullable=True))
    op.add_column("defects", sa.Column("ai_model_source", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("defects", "ai_model_source")
    op.drop_column("defects", "ai_severity_score")
    op.drop_column("defects", "ai_bbox")
    op.drop_column("defects", "ai_confidence")
