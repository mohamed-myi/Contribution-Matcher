"""Performance optimization indexes and materialized views.

Revision ID: perf_opt_001
Revises: b8fc862e3324
Create Date: 2024-12-10 00:00:00.000000

Optimizations:
- Composite indexes for common query patterns
- Partial indexes for active issues
- Indexes for scoring and filtering
- Materialized view for top matches (PostgreSQL only)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'perf_opt_001'
down_revision: Union[str, None] = 'b8fc862e3324'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance optimization indexes."""
    
    # Get connection to determine database type
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # ==========================================================================
    # Composite Indexes for Common Query Patterns
    # ==========================================================================
    
    # Issues: User + Active + Score (for top matches)
    op.create_index(
        'ix_issues_user_active_score',
        'issues',
        ['user_id', 'is_active', 'cached_score'],
        postgresql_where=sa.text('is_active = true'),
    )
    
    # Issues: User + Active + Created (for recent issues)
    op.create_index(
        'ix_issues_user_active_created',
        'issues',
        ['user_id', 'is_active', 'created_at'],
        postgresql_where=sa.text('is_active = true'),
    )
    
    # Issues: User + Difficulty (for filtering)
    op.create_index(
        'ix_issues_user_difficulty',
        'issues',
        ['user_id', 'difficulty'],
    )
    
    # Issues: User + Issue Type (for filtering)
    op.create_index(
        'ix_issues_user_issue_type',
        'issues',
        ['user_id', 'issue_type'],
    )
    
    # Issues: User + Label (for ML training data)
    op.create_index(
        'ix_issues_user_label',
        'issues',
        ['user_id', 'label'],
        postgresql_where=sa.text("label IS NOT NULL"),
    )
    
    # Issues: URL (for deduplication lookups)
    op.create_index(
        'ix_issues_url_lookup',
        'issues',
        ['url'],
    )
    
    # ==========================================================================
    # Technology Indexes
    # ==========================================================================
    
    # IssueTechnology: Issue + Technology (for tech filtering)
    op.create_index(
        'ix_issue_technologies_issue_tech',
        'issue_technologies',
        ['issue_id', 'technology'],
    )
    
    # IssueTechnology: Technology lower case (for case-insensitive search)
    if is_postgresql:
        op.execute(
            """
            CREATE INDEX ix_issue_technologies_tech_lower
            ON issue_technologies (LOWER(technology));
            """
        )
    
    # ==========================================================================
    # Bookmark Indexes
    # ==========================================================================
    
    # IssueBookmark: User + Created (for recent bookmarks)
    op.create_index(
        'ix_issue_bookmarks_user_created',
        'issue_bookmarks',
        ['user_id', 'created_at'],
    )
    
    # ==========================================================================
    # Label Indexes (for ML)
    # ==========================================================================
    
    # IssueLabel: User + Label (for training data retrieval)
    op.create_index(
        'ix_issue_labels_user_label',
        'issue_labels',
        ['user_id', 'label'],
    )
    
    # ==========================================================================
    # Feature Cache Indexes
    # ==========================================================================
    
    # IssueFeatureCache: Profile updated (for cache invalidation)
    op.create_index(
        'ix_issue_feature_cache_profile_updated',
        'issue_feature_cache',
        ['profile_updated_at'],
    )
    
    # ==========================================================================
    # Staleness Indexes
    # ==========================================================================
    
    # Issues: Last verified (for staleness checks)
    op.create_index(
        'ix_issues_last_verified',
        'issues',
        ['last_verified_at'],
        postgresql_where=sa.text('is_active = true'),
    )
    
    # ==========================================================================
    # Materialized View for Top Matches (PostgreSQL only)
    # ==========================================================================
    
    if is_postgresql:
        # Create materialized view for top 100 matches per user
        # This dramatically speeds up the top-matches endpoint
        op.execute(
            """
            CREATE MATERIALIZED VIEW IF NOT EXISTS mv_top_matches AS
            SELECT 
                i.id as issue_id,
                i.user_id,
                i.title,
                i.url,
                i.repo_owner,
                i.repo_name,
                i.difficulty,
                i.issue_type,
                i.cached_score,
                i.repo_stars,
                i.created_at,
                ROW_NUMBER() OVER (
                    PARTITION BY i.user_id 
                    ORDER BY i.cached_score DESC NULLS LAST
                ) as rank
            FROM issues i
            WHERE i.is_active = true
              AND i.cached_score IS NOT NULL;
            """
        )
        
        # Create unique index for concurrent refresh
        op.execute(
            """
            CREATE UNIQUE INDEX ON mv_top_matches (user_id, issue_id);
            """
        )
        
        # Create index for fast user lookup
        op.execute(
            """
            CREATE INDEX ON mv_top_matches (user_id, rank);
            """
        )
        
        # Create function to refresh materialized view
        op.execute(
            """
            CREATE OR REPLACE FUNCTION refresh_top_matches()
            RETURNS void AS $$
            BEGIN
                REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top_matches;
            END;
            $$ LANGUAGE plpgsql;
            """
        )


def downgrade() -> None:
    """Remove performance optimization indexes."""
    
    connection = op.get_bind()
    is_postgresql = connection.dialect.name == 'postgresql'
    
    # Drop materialized view (PostgreSQL only)
    if is_postgresql:
        op.execute("DROP FUNCTION IF EXISTS refresh_top_matches();")
        op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_top_matches;")
        op.execute("DROP INDEX IF EXISTS ix_issue_technologies_tech_lower;")
    
    # Drop indexes
    op.drop_index('ix_issues_last_verified', table_name='issues')
    op.drop_index('ix_issue_feature_cache_profile_updated', table_name='issue_feature_cache')
    op.drop_index('ix_issue_labels_user_label', table_name='issue_labels')
    op.drop_index('ix_issue_bookmarks_user_created', table_name='issue_bookmarks')
    op.drop_index('ix_issue_technologies_issue_tech', table_name='issue_technologies')
    op.drop_index('ix_issues_url_lookup', table_name='issues')
    op.drop_index('ix_issues_user_label', table_name='issues')
    op.drop_index('ix_issues_user_issue_type', table_name='issues')
    op.drop_index('ix_issues_user_difficulty', table_name='issues')
    op.drop_index('ix_issues_user_active_created', table_name='issues')
    op.drop_index('ix_issues_user_active_score', table_name='issues')
