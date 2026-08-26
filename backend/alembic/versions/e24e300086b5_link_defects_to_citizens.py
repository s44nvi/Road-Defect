"""link defects to citizens

Adds an optional citizen ownership link to defects so authenticated
citizens can retrieve only the reports they personally submitted.

Existing defects and development/seed data remain valid because the
column is nullable.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e24e300086b5"
down_revision: Union[str, Sequence[str], None] = "a3d7e91f4c6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add optional citizen ownership to defects."""
    op.add_column(
        "defects",
        sa.Column("citizen_id", sa.Integer(), nullable=True),
    )

    op.create_index(
        "ix_defects_citizen_id",
        "defects",
        ["citizen_id"],
        unique=False,
    )

    op.create_foreign_key(
        "fk_defects_citizen_id_citizens",
        "defects",
        "citizens",
        ["citizen_id"],
        ["id"],
    )


def downgrade() -> None:
    """Remove citizen ownership from defects."""
    op.drop_constraint(
        "fk_defects_citizen_id_citizens",
        "defects",
        type_="foreignkey",
    )

    op.drop_index(
        "ix_defects_citizen_id",
        table_name="defects",
    )

    op.drop_column("defects", "citizen_id")