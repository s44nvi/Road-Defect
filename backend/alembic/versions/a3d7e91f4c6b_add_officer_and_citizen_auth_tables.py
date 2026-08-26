"""add officer and citizen auth tables

Adds the two identity tables backing municipal officer authentication:

  * officers -- municipal officer accounts (email/password_hash), used by
               POST /auth/officer/login and Depends(get_current_officer)
  * citizens -- citizen accounts, used by POST /auth/citizen/login

These are deliberately separate tables with no foreign key between them:
officer and citizen credentials must never authenticate against each
other's table. This migration is purely additive -- it creates two new
tables, adds no columns to and drops nothing from any existing table.

Revision ID: a3d7e91f4c6b
Revises: f1a9c3d5e7b2
Create Date: 2026-08-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3d7e91f4c6b'
down_revision: Union[str, Sequence[str], None] = 'f1a9c3d5e7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'officers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('department', sa.String(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_officers_id'), 'officers', ['id'], unique=False)
    op.create_index(op.f('ix_officers_email'), 'officers', ['email'], unique=True)

    op.create_table(
        'citizens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_citizens_id'), 'citizens', ['id'], unique=False)
    op.create_index(op.f('ix_citizens_email'), 'citizens', ['email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_citizens_email'), table_name='citizens')
    op.drop_index(op.f('ix_citizens_id'), table_name='citizens')
    op.drop_table('citizens')

    op.drop_index(op.f('ix_officers_email'), table_name='officers')
    op.drop_index(op.f('ix_officers_id'), table_name='officers')
    op.drop_table('officers')
