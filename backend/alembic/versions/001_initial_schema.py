"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2026-08-27
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create PostGIS extension
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create enums
    defect_type = postgresql.ENUM('pothole', 'crack', 'manhole', 'debris', 'hawker', 'fallen_tree', name='defecttype')
    defect_status = postgresql.ENUM('detected', 'verified', 'scheduled', 'repaired', 'validated', 'rejected', name='defectstatus')
    severity_level = postgresql.ENUM('low', 'medium', 'high', 'critical', name='severitylevel')
    
    defect_type.create(op.get_bind())
    defect_status.create(op.get_bind())
    severity_level.create(op.get_bind())
    
    # Create defects table
    op.create_table(
        'defects',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('defect_type', defect_type, nullable=False),
        sa.Column('status', defect_status, nullable=False, server_default='detected'),
        sa.Column('severity', severity_level, nullable=False),
        sa.Column('priority_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('evidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('recurrence_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('location', sa.Geometry('POINT', from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('verified_at', sa.DateTime()),
        sa.Column('verified_by', postgresql.UUID(as_uuid=True)),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_defects_status', 'defects', ['status'])
    op.create_index('ix_defects_created_at', 'defects', ['created_at'])
    op.create_index('ix_defects_priority_score', 'defects', ['priority_score'])
    op.execute('CREATE INDEX ix_defects_location ON defects USING GIST(location)')
    
    # Create observations table
    op.create_table(
        'observations',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('defect_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location', sa.Geometry('POINT', from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
        sa.Column('detection_confidence', sa.Float(), nullable=False),
        sa.Column('impact_magnitude', sa.Float()),
        sa.Column('image_urls', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('video_url', sa.String()),
        sa.Column('device_id', sa.String(), nullable=False),
        sa.Column('gps_accuracy', sa.Float()),
        sa.Column('heading', sa.Float()),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['defect_id'], ['defects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_observations_defect_id', 'observations', ['defect_id'])
    op.create_index('ix_observations_timestamp', 'observations', ['timestamp'])
    op.create_index('ix_observations_device_id', 'observations', ['device_id'])
    op.execute('CREATE INDEX ix_observations_location ON observations USING GIST(location)')
    
    # Create officers table
    op.create_table(
        'officers',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('username', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('role', sa.String(50), nullable=False, server_default='officer'),
        sa.Column('full_name', sa.String(255)),
        sa.Column('phone', sa.String(20)),
        sa.Column('assigned_area', sa.Geometry('POLYGON', from_text='ST_GeomFromEWKT', name='geometry')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_login', sa.DateTime()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email')
    )
    op.create_index('ix_officers_username', 'officers', ['username'])
    op.create_index('ix_officers_email', 'officers', ['email'])
    
    # Create repairs table
    op.create_table(
        'repairs',
        sa.Column('id', postgresql.UUID(as_uuid=True), server_default=sa.text('uuid_generate_v4()'), nullable=False),
        sa.Column('defect_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='scheduled'),
        sa.Column('assigned_crew', sa.String(255)),
        sa.Column('estimated_cost', sa.Float()),
        sa.Column('scheduled_date', sa.DateTime()),
        sa.Column('start_date', sa.DateTime()),
        sa.Column('completion_date', sa.DateTime()),
        sa.Column('before_image_urls', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('after_image_urls', postgresql.ARRAY(sa.String()), nullable=False, server_default='{}'),
        sa.Column('notes', sa.Text()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['defect_id'], ['defects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_repairs_defect_id', 'repairs', ['defect_id'])
    
    # Add foreign key for verified_by in defects
    op.create_foreign_key('fk_defects_verified_by', 'defects', 'officers', ['verified_by'], ['id'])


def downgrade() -> None:
    # Drop foreign keys
    op.drop_constraint('fk_defects_verified_by', 'defects')
    
    # Drop tables
    op.drop_table('repairs')
    op.drop_table('observations')
    op.drop_table('defects')
    op.drop_table('officers')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS defecttype')
    op.execute('DROP TYPE IF EXISTS defectstatus')
    op.execute('DROP TYPE IF EXISTS severitylevel')
