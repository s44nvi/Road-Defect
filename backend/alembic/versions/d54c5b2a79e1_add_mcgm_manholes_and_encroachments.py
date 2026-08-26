"""add MCGM manholes and encroachments

Revision ID: d54c5b2a79e1
Revises: c2f4a9e1b8d3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d54c5b2a79e1"
down_revision: Union[str, Sequence[str], None] = "c2f4a9e1b8d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "manholes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "object_id",
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column("road_name", sa.String(length=255), nullable=True),
        sa.Column("ward", sa.String(length=50), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("condition", sa.String(length=100), nullable=True),
        sa.Column("survey_date", sa.DateTime(), nullable=True),
        sa.Column("created_date", sa.DateTime(), nullable=True),
        sa.Column("last_edited_date", sa.DateTime(), nullable=True),
        sa.Column("remarks", sa.String(length=1000), nullable=True),
        sa.Column("road_norm", sa.String(length=255), nullable=True),
        sa.Column(
            "road_segment_id",
            sa.Integer(),
            sa.ForeignKey("road_segments.id"),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_manholes_object_id",
        "manholes",
        ["object_id"],
        unique=True,
    )
    op.create_index(
        "ix_manholes_road_segment_id",
        "manholes",
        ["road_segment_id"],
        unique=False,
    )

    op.create_table(
        "encroachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "object_id",
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column("road_name", sa.String(length=255), nullable=True),
        sa.Column("ward", sa.String(length=50), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("complaint_type", sa.String(length=255), nullable=True),
        sa.Column("description", sa.String(length=2000), nullable=True),
        sa.Column("created_date", sa.DateTime(), nullable=True),
        sa.Column("last_edited_date", sa.DateTime(), nullable=True),
        sa.Column(
            "road_segment_id",
            sa.Integer(),
            sa.ForeignKey("road_segments.id"),
            nullable=True,
        ),
    )

    op.create_index(
        "ix_encroachments_object_id",
        "encroachments",
        ["object_id"],
        unique=True,
    )
    op.create_index(
        "ix_encroachments_road_segment_id",
        "encroachments",
        ["road_segment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_encroachments_road_segment_id",
        table_name="encroachments",
    )
    op.drop_index(
        "ix_encroachments_object_id",
        table_name="encroachments",
    )
    op.drop_table("encroachments")

    op.drop_index(
        "ix_manholes_road_segment_id",
        table_name="manholes",
    )
    op.drop_index(
        "ix_manholes_object_id",
        table_name="manholes",
    )
    op.drop_table("manholes")