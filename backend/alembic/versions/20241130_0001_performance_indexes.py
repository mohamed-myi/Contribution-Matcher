"""add performance indexes and cached_score column

Revision ID: 20241130_0001
Revises: 455e55f862ec
Create Date: 2024-11-30

This migration adds:
1. Compound indexes for common query patterns
2. cached_score column for precomputed issue scores
3. Additional indexes for performance optimization

Performance improvements:
- ix_issues_user_created: Speeds up paginated issue queries (ORDER BY created_at)
- ix_issues_user_difficulty: Speeds up difficulty filter queries
- ix_issues_user_active: Speeds up active issue queries
- ix_bookmarks_user_issue: Speeds up bookmark status lookups
- ix_issues_cached_score: Speeds up top matches queries
"""

from alembic import op
import sqlalchemy as sa


revision = "20241130_0001"
down_revision = "455e55f862ec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==========================================================================
    # 1. Add cached_score column for precomputed scores
    # ==========================================================================
    op.add_column(
        "issues",
        sa.Column(
            "cached_score",
            sa.Float(),
            nullable=True,
            comment="Precomputed match score for faster queries",
        ),
    )

    # ==========================================================================
    # 2. Compound indexes for common query patterns
    # ==========================================================================

    # Issues: user_id + created_at (for paginated queries)
    op.create_index(
        "ix_issues_user_created",
        "issues",
        ["user_id", "created_at"],
        unique=False,
    )

    # Issues: user_id + difficulty (for filtered queries)
    op.create_index(
        "ix_issues_user_difficulty",
        "issues",
        ["user_id", "difficulty"],
        unique=False,
    )

    # Issues: user_id + is_active (for active issue queries)
    op.create_index(
        "ix_issues_user_active",
        "issues",
        ["user_id", "is_active"],
        unique=False,
    )

    # Issues: user_id + cached_score (for top matches)
    op.create_index(
        "ix_issues_user_score",
        "issues",
        ["user_id", "cached_score"],
        unique=False,
    )

    # Issues: cached_score alone (for global ranking)
    op.create_index(
        "ix_issues_cached_score",
        "issues",
        ["cached_score"],
        unique=False,
    )

    # ==========================================================================
    # 3. Bookmark indexes for faster lookups
    # ==========================================================================

    # Bookmarks: user_id + issue_id (already has unique constraint, but adding index for reads)
    op.create_index(
        "ix_bookmarks_user_issue",
        "issue_bookmarks",
        ["user_id", "issue_id"],
        unique=False,
    )

    # ==========================================================================
    # 4. Issue technologies index
    # ==========================================================================

    # Technologies: issue_id + technology (for tech-based queries)
    op.create_index(
        "ix_technologies_issue_tech",
        "issue_technologies",
        ["issue_id", "technology"],
        unique=False,
    )

    # ==========================================================================
    # 5. User indexes
    # ==========================================================================

    # Users: github_username (for username lookups - may already exist)
    try:
        op.create_index(
            "ix_users_github_username",
            "users",
            ["github_username"],
            unique=True,
        )
    except Exception:
        pass  # Index may already exist from unique constraint

    # ==========================================================================
    # 6. Issue labels index for ML training queries
    # ==========================================================================

    op.create_index(
        "ix_issue_labels_user_label",
        "issue_labels",
        ["user_id", "label"],
        unique=False,
    )

    # ==========================================================================
    # 7. Issue notes table (new)
    # ==========================================================================

    # Check if table exists first
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "issue_notes" not in inspector.get_table_names():
        op.create_table(
            "issue_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "issue_id",
                sa.Integer(),
                sa.ForeignKey("issues.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        )

        op.create_index(
            "ix_issue_notes_user_issue",
            "issue_notes",
            ["user_id", "issue_id"],
            unique=False,
        )

    # ==========================================================================
    # 8. Token blacklist table for JWT invalidation
    # ==========================================================================

    if "token_blacklist" not in inspector.get_table_names():
        op.create_table(
            "token_blacklist",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_jti", sa.String(length=256), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        )

        op.create_index(
            "ix_token_blacklist_jti",
            "token_blacklist",
            ["token_jti"],
            unique=True,
        )

        op.create_index(
            "ix_token_blacklist_expires_at",
            "token_blacklist",
            ["expires_at"],
            unique=False,
        )

    # ==========================================================================
    # 9. Repository metadata table (for GraphQL cache)
    # ==========================================================================

    if "repo_metadata" not in inspector.get_table_names():
        op.create_table(
            "repo_metadata",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("repo_owner", sa.String(length=255), nullable=False),
            sa.Column("repo_name", sa.String(length=255), nullable=False),
            sa.Column("stars", sa.Integer()),
            sa.Column("forks", sa.Integer()),
            sa.Column("languages", sa.JSON()),
            sa.Column("topics", sa.JSON()),
            sa.Column("last_commit_date", sa.String(length=64)),
            sa.Column("contributor_count", sa.Integer()),
            sa.Column("cached_at", sa.DateTime(), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.UniqueConstraint("repo_owner", "repo_name", name="uq_repo_metadata_owner_name"),
        )

        op.create_index(
            "ix_repo_metadata_owner_name",
            "repo_metadata",
            ["repo_owner", "repo_name"],
            unique=True,
        )


def downgrade() -> None:
    # Drop new tables
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "repo_metadata" in inspector.get_table_names():
        op.drop_index("ix_repo_metadata_owner_name", table_name="repo_metadata")
        op.drop_table("repo_metadata")

    if "token_blacklist" in inspector.get_table_names():
        op.drop_index("ix_token_blacklist_expires_at", table_name="token_blacklist")
        op.drop_index("ix_token_blacklist_jti", table_name="token_blacklist")
        op.drop_table("token_blacklist")

    if "issue_notes" in inspector.get_table_names():
        op.drop_index("ix_issue_notes_user_issue", table_name="issue_notes")
        op.drop_table("issue_notes")

    # Drop indexes
    op.drop_index("ix_issue_labels_user_label", table_name="issue_labels")

    try:
        op.drop_index("ix_users_github_username", table_name="users")
    except Exception:
        pass

    op.drop_index("ix_technologies_issue_tech", table_name="issue_technologies")
    op.drop_index("ix_bookmarks_user_issue", table_name="issue_bookmarks")
    op.drop_index("ix_issues_cached_score", table_name="issues")
    op.drop_index("ix_issues_user_score", table_name="issues")
    op.drop_index("ix_issues_user_active", table_name="issues")
    op.drop_index("ix_issues_user_difficulty", table_name="issues")
    op.drop_index("ix_issues_user_created", table_name="issues")

    # Drop cached_score column
    op.drop_column("issues", "cached_score")
