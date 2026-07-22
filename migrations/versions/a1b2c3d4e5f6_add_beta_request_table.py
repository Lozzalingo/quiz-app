"""Add beta_request table

Revision ID: a1b2c3d4e5f6
Revises: f76c892c2474
Create Date: 2026-04-28 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'f76c892c2474'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('beta_request',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('beta_request')
