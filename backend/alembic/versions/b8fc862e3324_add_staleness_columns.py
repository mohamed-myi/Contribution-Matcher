"""add_staleness_columns

Revision ID: b8fc862e3324
Revises: 20241202_0001
Create Date: 2024-12-02

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8fc862e3324'
down_revision = '20241202_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add staleness tracking columns to issues table
    op.add_column('issues', sa.Column('last_verified_at', sa.DateTime(), nullable=True))
    op.add_column('issues', sa.Column('closed_at', sa.DateTime(), nullable=True))
    op.add_column('issues', sa.Column('close_reason', sa.String(32), nullable=True))
    op.add_column('issues', sa.Column('github_state', sa.String(16), nullable=True))


def downgrade() -> None:
    # Remove staleness tracking columns from issues table
    op.drop_column('issues', 'github_state')
    op.drop_column('issues', 'close_reason')
    op.drop_column('issues', 'closed_at')
    op.drop_column('issues', 'last_verified_at')
