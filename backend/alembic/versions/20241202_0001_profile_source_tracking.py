"""add profile source tracking columns

Revision ID: 20241202_0001
Revises: 20241130_0001
Create Date: 2024-12-02

This migration adds:
1. profile_source column to track where profile data came from
2. last_github_sync column to track when profile was last synced from GitHub

Profile sources:
- "github": Profile created/synced from GitHub
- "resume": Profile created from uploaded resume
- "manual": Profile manually created or edited
"""

from alembic import op
import sqlalchemy as sa


revision = "20241202_0001"
down_revision = "20241130_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add profile_source column with default "manual" for existing profiles
    op.add_column(
        "dev_profile",
        sa.Column(
            "profile_source",
            sa.String(length=20),
            nullable=False,
            server_default="manual",
            comment="Origin of profile data: github, resume, or manual",
        ),
    )
    
    # Add last_github_sync column (nullable - only set for GitHub-sourced profiles)
    op.add_column(
        "dev_profile",
        sa.Column(
            "last_github_sync",
            sa.DateTime(),
            nullable=True,
            comment="Timestamp of last GitHub profile sync",
        ),
    )
    
    # Create index on profile_source for filtering queries
    op.create_index(
        "ix_dev_profile_source",
        "dev_profile",
        ["profile_source"],
        unique=False,
    )


def downgrade() -> None:
    # Drop index
    op.drop_index("ix_dev_profile_source", table_name="dev_profile")
    
    # Drop columns
    op.drop_column("dev_profile", "last_github_sync")
    op.drop_column("dev_profile", "profile_source")

