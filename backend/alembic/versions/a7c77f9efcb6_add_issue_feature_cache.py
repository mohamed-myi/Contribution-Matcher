"""add_issue_feature_cache"""

from alembic import op
import sqlalchemy as sa


revision = "a7c77f9efcb6"
down_revision = "20231129_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issue_feature_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), unique=True),
        sa.Column("profile_updated_at", sa.DateTime(), nullable=True),
        sa.Column("issue_updated_at", sa.DateTime(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("skill_match_pct", sa.Float(), nullable=True),
        sa.Column("experience_score", sa.Float(), nullable=True),
        sa.Column("repo_quality_score", sa.Float(), nullable=True),
        sa.Column("freshness_score", sa.Float(), nullable=True),
        sa.Column("time_match_score", sa.Float(), nullable=True),
        sa.Column("interest_match_score", sa.Float(), nullable=True),
        sa.Column("total_score", sa.Float(), nullable=True),
        sa.Column("feature_vector", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("issue_feature_cache")

