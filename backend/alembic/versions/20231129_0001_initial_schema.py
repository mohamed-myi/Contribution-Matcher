"""initial schema

Revision ID: 20231129_0001
Revises:
Create Date: 2025-11-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20231129_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("github_id", sa.String(length=255), nullable=False, unique=True),
        sa.Column("github_username", sa.String(length=255), nullable=False, unique=True),
        sa.Column("email", sa.String(length=255)),
        sa.Column("avatar_url", sa.String(length=512)),
        sa.Column("github_access_token", sa.String(length=512)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "dev_profile",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True),
        sa.Column("skills", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("experience_level", sa.String(length=50)),
        sa.Column("interests", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("preferred_languages", sa.JSON(), server_default=sa.text("'[]'")),
        sa.Column("time_availability_hours_per_week", sa.Integer()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "issues",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("repo_owner", sa.String(length=255)),
        sa.Column("repo_name", sa.String(length=255)),
        sa.Column("repo_url", sa.String(length=512)),
        sa.Column("difficulty", sa.String(length=64)),
        sa.Column("issue_type", sa.String(length=64)),
        sa.Column("time_estimate", sa.String(length=64)),
        sa.Column("labels", sa.JSON()),
        sa.Column("repo_stars", sa.Integer()),
        sa.Column("repo_forks", sa.Integer()),
        sa.Column("repo_languages", sa.JSON()),
        sa.Column("repo_topics", sa.JSON()),
        sa.Column("last_commit_date", sa.String(length=64)),
        sa.Column("contributor_count", sa.Integer()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("label", sa.String(length=16)),
        sa.Column("labeled_at", sa.DateTime()),
        sa.UniqueConstraint("user_id", "url", name="uq_issues_user_url"),
    )

    op.create_table(
        "issue_technologies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE")),
        sa.Column("technology", sa.String(length=255), nullable=False),
        sa.Column("technology_category", sa.String(length=255)),
    )

    op.create_table(
        "issue_bookmarks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "issue_id", name="uq_issue_bookmarks_user_issue"),
    )

    op.create_table(
        "issue_labels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE")),
        sa.Column("label", sa.String(length=8), nullable=False),
        sa.Column("labeled_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "issue_id", name="uq_issue_labels_user_issue"),
    )

    op.create_table(
        "issue_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("issues.id", ondelete="CASCADE"), unique=True),
        sa.Column("description_embedding", sa.LargeBinary()),
        sa.Column("title_embedding", sa.LargeBinary()),
        sa.Column("embedding_model", sa.String(length=255), server_default="all-MiniLM-L6-v2"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "user_ml_models",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("model_path", sa.String(length=512), nullable=False),
        sa.Column("scaler_path", sa.String(length=512)),
        sa.Column("metrics", sa.JSON()),
        sa.Column("trained_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_ml_models")
    op.drop_table("issue_embeddings")
    op.drop_table("issue_labels")
    op.drop_table("issue_bookmarks")
    op.drop_table("issue_technologies")
    op.drop_table("issues")
    op.drop_table("dev_profile")
    op.drop_table("users")
