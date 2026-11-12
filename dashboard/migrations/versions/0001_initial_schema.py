"""initial schema: users, services, deployments, incidents

Revision ID: 0001_initial
Revises: 
Create Date: 2026-11-12

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    
    op.create_table('services',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('repository_url', sa.String(length=255), nullable=True),
    sa.Column('health_check_url', sa.String(length=255), nullable=True),
    sa.Column('environment', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('owner', sa.String(length=100), nullable=True),
    sa.Column('last_health_status', sa.String(length=20), nullable=True),
    sa.Column('last_health_check_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_services_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_services_name'), ['name'], unique=True)

    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('last_login_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_email'), ['email'], unique=True)
        batch_op.create_index(batch_op.f('ix_users_username'), ['username'], unique=True)

    op.create_table('deployments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=False),
    sa.Column('commit_id', sa.String(length=64), nullable=False),
    sa.Column('commit_author', sa.String(length=120), nullable=False),
    sa.Column('commit_message', sa.Text(), nullable=False),
    sa.Column('build_number', sa.Integer(), nullable=False),
    sa.Column('image_tag', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('environment', sa.String(length=20), nullable=False),
    sa.Column('duration_seconds', sa.Integer(), nullable=True),
    sa.Column('triggered_by', sa.String(length=64), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('deployments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_deployments_commit_id'), ['commit_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deployments_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_deployments_service_id'), ['service_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_deployments_status'), ['status'], unique=False)

    op.create_table('incidents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('severity', sa.String(length=20), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('service_id', sa.Integer(), nullable=True),
    sa.Column('deployment_id', sa.Integer(), nullable=True),
    sa.Column('auto_generated', sa.Boolean(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['service_id'], ['services.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_incidents_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_service_id'), ['service_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_severity'), ['severity'], unique=False)
        batch_op.create_index(batch_op.f('ix_incidents_status'), ['status'], unique=False)

    


def downgrade():
    
    with op.batch_alter_table('incidents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incidents_status'))
        batch_op.drop_index(batch_op.f('ix_incidents_severity'))
        batch_op.drop_index(batch_op.f('ix_incidents_service_id'))
        batch_op.drop_index(batch_op.f('ix_incidents_created_at'))

    op.drop_table('incidents')
    with op.batch_alter_table('deployments', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_deployments_status'))
        batch_op.drop_index(batch_op.f('ix_deployments_service_id'))
        batch_op.drop_index(batch_op.f('ix_deployments_created_at'))
        batch_op.drop_index(batch_op.f('ix_deployments_commit_id'))

    op.drop_table('deployments')
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_username'))
        batch_op.drop_index(batch_op.f('ix_users_email'))
        batch_op.drop_index(batch_op.f('ix_users_created_at'))

    op.drop_table('users')
    with op.batch_alter_table('services', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_services_name'))
        batch_op.drop_index(batch_op.f('ix_services_created_at'))

    op.drop_table('services')
    
