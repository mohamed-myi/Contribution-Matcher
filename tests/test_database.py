"""
Tests for database operations and queries.
"""
import json
from datetime import datetime, timedelta

import pytest

from core.database import (
    get_repo_metadata,
    init_db,
    replace_issue_technologies,
    update_issue_label,
    upsert_issue,
    upsert_repo_metadata,
    export_to_csv,
    export_to_json,
    get_issue_technologies,
    get_labeling_statistics,
    get_statistics,
    query_issues,
    query_unlabeled_issues,
)


class TestDatabaseOperations:
    """Tests for basic database operations."""
    
    def test_init_db_creates_tables(self, test_db):
        """Test that init_db creates all required tables."""
        from core.database import db_conn
        
        with db_conn() as conn:
            cur = conn.cursor()
            
            # Check that tables exist
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cur.fetchall()]
            
            assert "issues" in tables
            assert "issue_technologies" in tables
            assert "repo_metadata" in tables
            assert "dev_profile" in tables
    
    def test_upsert_issue_insert(self, test_db):
        """Test inserting a new issue."""
        issue_id = upsert_issue(
            title="Test Issue",
            url="https://github.com/test/repo/issues/1",
            body="Test body",
            repo_owner="test",
            repo_name="repo",
        )
        
        assert issue_id > 0
        
        # Verify it was inserted
        from core.database import db_conn
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM issues WHERE id = ?", (issue_id,))
            row = cur.fetchone()
            assert row is not None
            assert row[1] == "Test Issue"  # title is second column
    
    def test_upsert_issue_update(self, test_db):
        """Test updating an existing issue."""
        # Insert first
        issue_id = upsert_issue(
            title="Original Title",
            url="https://github.com/test/repo/issues/1",
            body="Original body",
        )
        
        # Update
        updated_id = upsert_issue(
            title="Updated Title",
            url="https://github.com/test/repo/issues/1",  # Same URL
            body="Updated body",
        )
        
        assert updated_id == issue_id  # Should be same ID
        
        # Verify update
        from core.database import db_conn
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT title FROM issues WHERE id = ?", (issue_id,))
            title = cur.fetchone()[0]
            assert title == "Updated Title"
    
    def test_replace_issue_technologies(self, test_db):
        """Test replacing issue technologies."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
        )
        
        # Add technologies
        replace_issue_technologies(issue_id, [
            ("python", "backend"),
            ("django", "backend"),
        ])
        
        # Verify
        techs = get_issue_technologies(issue_id)
        assert len(techs) == 2
        tech_names = [t[0] for t in techs]
        assert "python" in tech_names
        assert "django" in tech_names
        
        # Replace with new technologies
        replace_issue_technologies(issue_id, [
            ("react", "frontend"),
        ])
        
        # Verify old ones are gone
        techs = get_issue_technologies(issue_id)
        assert len(techs) == 1
        assert techs[0][0] == "react"
    
    def test_update_issue_label(self, test_db):
        """Test updating issue label."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
        )
        
        # Update label
        result = update_issue_label(issue_id, "good")
        assert result is True
        
        # Verify
        from core.database import db_conn
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT label FROM issues WHERE id = ?", (issue_id,))
            label = cur.fetchone()[0]
            assert label == "good"
    
    def test_update_issue_label_invalid(self, test_db):
        """Test updating with invalid label."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
        )
        
        result = update_issue_label(issue_id, "invalid")
        assert result is False
    
    def test_upsert_repo_metadata(self, test_db):
        """Test caching repo metadata."""
        upsert_repo_metadata(
            repo_owner="testowner",
            repo_name="testrepo",
            stars=100,
            forks=20,
            languages={"Python": 50000},
            topics=["python", "django"],
        )
        
        # Retrieve
        metadata = get_repo_metadata("testowner", "testrepo")
        assert metadata is not None
        assert metadata["stars"] == 100
        assert metadata["forks"] == 20
        assert "Python" in metadata["languages"]


class TestQueryIssues:
    """Tests for issue querying."""
    
    def test_query_all_issues(self, test_db, multiple_issues_in_db):
        """Test querying all issues."""
        issues = query_issues()
        assert len(issues) == 3
    
    def test_query_by_difficulty(self, test_db, multiple_issues_in_db):
        """Test filtering by difficulty."""
        issues = query_issues(difficulty="beginner")
        assert len(issues) == 2  # Two beginner issues
        assert all(i["difficulty"] == "beginner" for i in issues)
    
    def test_query_by_issue_type(self, test_db, multiple_issues_in_db):
        """Test filtering by issue type."""
        issues = query_issues(issue_type="bug")
        assert len(issues) == 1
        assert issues[0]["issue_type"] == "bug"
    
    def test_query_with_limit(self, test_db, multiple_issues_in_db):
        """Test limiting results."""
        issues = query_issues(limit=2)
        assert len(issues) == 2
    
    def test_query_with_offset(self, test_db, multiple_issues_in_db):
        """Test pagination with offset."""
        all_issues = query_issues()
        offset_issues = query_issues(offset=1, limit=2)
        
        assert len(offset_issues) == 2
        # First issue in offset result should be second in all results
        assert offset_issues[0]["id"] == all_issues[1]["id"]
    
    def test_query_by_label(self, test_db, multiple_issues_in_db):
        """Test filtering by label."""
        # Label one issue
        issues = query_issues()
        update_issue_label(issues[0]["id"], "good")
        
        # Query by label
        good_issues = query_issues(label="good")
        assert len(good_issues) == 1


class TestGetStatistics:
    """Tests for statistics queries."""
    
    def test_get_statistics(self, test_db, multiple_issues_in_db):
        """Test getting aggregate statistics."""
        stats = get_statistics()
        
        assert stats["total_issues"] == 3
        assert "by_difficulty" in stats
        assert "active_issues" in stats
        assert "labeled_issues" in stats
    
    def test_statistics_empty_database(self, test_db):
        """Test statistics with empty database."""
        stats = get_statistics()
        
        assert stats["total_issues"] == 0
        assert stats["active_issues"] == 0
        assert stats["labeled_issues"] == 0


class TestLabelingQueries:
    """Tests for labeling-related queries."""
    
    def test_query_unlabeled_issues(self, test_db, multiple_issues_in_db):
        """Test querying unlabeled issues."""
        issues = query_unlabeled_issues()
        assert len(issues) == 3  # All should be unlabeled initially
    
    def test_query_unlabeled_with_labeled(self, test_db, multiple_issues_in_db):
        """Test querying unlabeled issues when some are labeled."""
        # Label one issue
        issues = query_issues()
        update_issue_label(issues[0]["id"], "good")
        
        # Query unlabeled
        unlabeled = query_unlabeled_issues()
        assert len(unlabeled) == 2
    
    def test_get_labeling_statistics(self, test_db, multiple_issues_in_db):
        """Test getting labeling statistics."""
        # Label some issues
        issues = query_issues()
        update_issue_label(issues[0]["id"], "good")
        update_issue_label(issues[1]["id"], "bad")
        
        stats = get_labeling_statistics()
        
        assert stats["total_labeled"] == 2
        assert "by_label" in stats
        assert stats["by_label"].get("good", 0) == 1
        assert stats["by_label"].get("bad", 0) == 1


class TestExport:
    """Tests for export functionality."""
    
    def test_export_to_csv(self, test_db, multiple_issues_in_db, tmp_path):
        """Test exporting issues to CSV."""
        output_file = tmp_path / "test_export.csv"
        
        count = export_to_csv(str(output_file))
        
        assert output_file.exists()
        assert count == 3
        
        # Verify CSV content
        import csv
        with open(output_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3
    
    def test_export_to_json(self, test_db, multiple_issues_in_db, tmp_path):
        """Test exporting issues to JSON."""
        output_file = tmp_path / "test_export.json"
        
        count = export_to_json(str(output_file))
        
        assert output_file.exists()
        assert count == 3
        
        # Verify JSON content
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            assert len(data) == 3
    
    def test_export_empty_database(self, test_db, tmp_path):
        """Test exporting from empty database."""
        output_file = tmp_path / "test_export.csv"
        
        count = export_to_csv(str(output_file))
        
        # Should return 0 for empty database
        assert count == 0
