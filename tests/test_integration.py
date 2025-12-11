"""
Integration tests for full CLI workflows.
"""

import json
import os
from unittest.mock import Mock, patch

from core.cli.contribution_matcher import (
    cmd_create_profile,
    cmd_discover,
    cmd_export,
    cmd_label_export,
    cmd_label_import,
    cmd_label_status,
    cmd_list,
    cmd_score,
    cmd_stats,
    cmd_train_model,
)


class TestDiscoverWorkflow:
    """Tests for issue discovery workflow."""

    @patch("core.cli.contribution_matcher.search_issues")
    @patch("core.cli.contribution_matcher.batch_get_repo_metadata")
    def test_discover_issues_workflow(self, mock_repo_meta, mock_search, test_db, monkeypatch):
        """Test complete issue discovery workflow."""
        test_db_path, _, _ = test_db

        # Set DATABASE_URL to use the test database so cmd_discover uses it
        test_db_url = f"sqlite:///{test_db_path}"
        monkeypatch.setenv("DATABASE_URL", test_db_url)

        # Reset and re-initialize the global db object with the test database URL
        from core.db import db

        if db.is_initialized:
            db.engine.dispose()
        db._initialized = False
        db.initialize(test_db_url)

        # Create a user with id=1 for the CLI to use (upsert_issue defaults to user_id=1)
        from core.models import User

        with db.session() as session:
            # Check if user already exists
            existing_user = session.query(User).filter(User.id == 1).first()
            if not existing_user:
                user = User(
                    id=1,
                    github_id="test_user_1",
                    github_username="testuser1",
                    email="test1@example.com",
                )
                session.add(user)
                session.commit()

        # Mock GitHub API responses
        mock_search.return_value = [
            {
                "id": 1,
                "title": "Test Issue",
                "body": "This is a test issue body with sufficient length to pass quality checks.",
                "html_url": "https://github.com/test/repo/issues/1",
                "url": "https://api.github.com/repos/test/repo/issues/1",
                "repository_url": "https://api.github.com/repos/test/repo",
                "labels": [{"name": "good first issue"}],
                "state": "open",
                "updated_at": "2024-01-01T00:00:00Z",
            }
        ]

        # batch_get_repo_metadata returns a dict mapping (owner, name) tuples to metadata
        mock_repo_meta.return_value = {
            ("test", "repo"): {
                "repo_owner": "test",
                "repo_name": "repo",
                "stars": 100,
                "forks": 20,
                "languages": {"Python": 50000},
                "topics": ["python"],
                "last_commit_date": "2024-01-01T00:00:00Z",
                "contributor_count": 5,
            }
        }

        # Create args object
        args = Mock()
        args.labels = None
        args.language = None
        args.stars = None
        args.limit = 10
        args.verbose = False
        args.no_quality_filters = False

        # Run discover command
        cmd_discover(args)

        # Verify issue was stored
        from core.database import query_issues

        issues = query_issues()
        assert len(issues) == 1
        assert issues[0]["title"] == "Test Issue"

    @patch("core.cli.contribution_matcher.search_issues")
    def test_discover_with_filters(self, mock_search, test_db):
        """Test discovery with filters."""
        mock_search.return_value = []

        args = Mock()
        args.labels = "good first issue,help wanted"
        args.language = "python"
        args.stars = 100
        args.limit = 50

        cmd_discover(args)

        # Verify search was called with correct parameters
        mock_search.assert_called_once()
        call_args = mock_search.call_args
        assert call_args[1]["language"] == "python"
        assert call_args[1]["min_stars"] == 100


class TestProfileWorkflow:
    """Tests for profile creation workflow."""

    @patch("core.cli.contribution_matcher.create_profile_from_github")
    def test_create_profile_from_github(self, mock_create, test_db):
        """Test creating profile from GitHub."""
        mock_create.return_value = {
            "skills": ["python"],
            "experience_level": "intermediate",
            "interests": [],
            "preferred_languages": ["python"],
        }

        args = Mock()
        args.github = "testuser"
        args.resume = None
        args.manual = False

        cmd_create_profile(args)

        mock_create.assert_called_once_with("testuser")

    def test_create_profile_manual(self, test_db, monkeypatch):
        """Test creating profile manually."""
        # Mock input
        inputs = iter(
            [
                "python, django, postgresql",
                "intermediate",
                "web development",
                "python, javascript",
                "10",
            ]
        )
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        args = Mock()
        args.github = None
        args.resume = None
        args.manual = True

        cmd_create_profile(args)

        # Verify profile was created
        from core.profile import load_dev_profile
        from core.profile.dev_profile import DEV_PROFILE_JSON

        profile = load_dev_profile()
        assert "python" in profile["skills"]
        assert profile["experience_level"] == "intermediate"

        # Cleanup - only remove the file created by this test
        if os.path.exists(DEV_PROFILE_JSON):
            os.remove(DEV_PROFILE_JSON)


class TestScoringWorkflow:
    """Tests for scoring workflow."""

    def test_score_issues_workflow(self, test_db, sample_profile, multiple_issues_in_db):
        """Test scoring issues against profile."""
        # Save profile
        from core.profile import save_dev_profile

        save_dev_profile(sample_profile)

        try:
            args = Mock()
            args.issue_id = None
            args.top = 2
            args.limit = None
            args.format = "text"
            args.verbose = False

            cmd_score(args)

            # Should complete without error
            # (We can't easily capture stdout in this test, but no exception = success)
        finally:
            # Cleanup
            from core.profile.dev_profile import DEV_PROFILE_JSON

            if os.path.exists(DEV_PROFILE_JSON):
                os.remove(DEV_PROFILE_JSON)

    def test_score_specific_issue(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test scoring a specific issue."""
        from core.profile import save_dev_profile

        save_dev_profile(sample_profile)

        try:
            from core.database import query_issues

            issues = query_issues()
            issue_id = issues[0]["id"]

            args = Mock()
            args.issue_id = issue_id
            args.top = None
            args.limit = None
            args.format = "text"
            args.verbose = False

            cmd_score(args)
        finally:
            # Cleanup
            from core.profile.dev_profile import DEV_PROFILE_JSON

            if os.path.exists(DEV_PROFILE_JSON):
                os.remove(DEV_PROFILE_JSON)


class TestLabelingWorkflow:
    """Tests for labeling workflow."""

    def test_label_export_import_workflow(
        self, test_db, multiple_issues_in_db, tmp_path, init_test_db
    ):
        """Test complete labeling workflow."""
        # Export unlabeled issues
        export_file = tmp_path / "labels.csv"

        args_export = Mock()
        args_export.output = str(export_file)
        args_export.difficulty = None
        args_export.limit = None

        cmd_label_export(args_export)

        assert export_file.exists()

        # Read CSV and add labels
        import csv

        rows = []
        with open(export_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row["label"] = "good" if "Beginner" in row.get("title", "") else "bad"
                rows.append(row)

        # Write back
        with open(export_file, "w", newline="", encoding="utf-8") as f:
            if rows:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

        # Import labels
        args_import = Mock()
        args_import.input = str(export_file)
        args_import.verbose = False

        cmd_label_import(args_import)

        # Verify labels were imported
        from core.database import get_labeling_statistics

        stats = get_labeling_statistics()
        assert stats["total_labeled"] > 0

    def test_label_status(self, test_db, multiple_issues_in_db, init_test_db):
        """Test label status command."""
        # Label one issue
        from core.database import query_issues, update_issue_label

        issues = query_issues()
        update_issue_label(issues[0]["id"], "good")

        args = Mock()
        cmd_label_status(args)

        # Should complete without error


class TestMLTrainingWorkflow:
    """Tests for ML training workflow."""

    def test_train_model_workflow(self, test_db, labeled_issues_for_ml, init_test_db):
        """Test complete ML training workflow."""
        # Add more labels to meet minimum
        from core.database import update_issue_label, upsert_issue

        for i in range(8):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 20}",
                body="Test",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        args = Mock()
        args.force = True

        try:
            cmd_train_model(args)

            # Verify model files were created
            assert os.path.exists("issue_classifier.pkl")
            assert os.path.exists("issue_scaler.pkl")
        finally:
            # Cleanup
            if os.path.exists("issue_classifier.pkl"):
                os.remove("issue_classifier.pkl")
            if os.path.exists("issue_scaler.pkl"):
                os.remove("issue_scaler.pkl")


class TestExportWorkflow:
    """Tests for export workflow."""

    def test_export_csv_workflow(self, test_db, multiple_issues_in_db, tmp_path, init_test_db):
        """Test exporting to CSV."""
        output_file = tmp_path / "export.csv"

        args = Mock()
        args.format = "csv"
        args.output = str(output_file)
        args.difficulty = None
        args.issue_type = None
        args.limit = 100

        cmd_export(args)

        assert output_file.exists()

        # Verify content
        import csv

        with open(output_file, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 3

    def test_export_json_workflow(self, test_db, multiple_issues_in_db, tmp_path, init_test_db):
        """Test exporting to JSON."""
        output_file = tmp_path / "export.json"

        args = Mock()
        args.format = "json"
        args.output = str(output_file)
        args.difficulty = None
        args.issue_type = None
        args.limit = 100

        cmd_export(args)

        assert output_file.exists()

        # Verify content
        with open(output_file, encoding="utf-8") as f:
            data = json.load(f)
            assert len(data) == 3


class TestListWorkflow:
    """Tests for listing issues."""

    def test_list_issues_workflow(self, test_db, multiple_issues_in_db, capsys, monkeypatch):
        """Test listing issues."""
        test_db_path, _, _ = test_db

        # Set DATABASE_URL to use the test database so cmd_list uses it
        test_db_url = f"sqlite:///{test_db_path}"
        monkeypatch.setenv("DATABASE_URL", test_db_url)
        # Reset and re-initialize the global db object with the test database URL
        from core.db import db

        if db.is_initialized:
            db.engine.dispose()
        db._initialized = False
        db.initialize(test_db_url)
        args = Mock()
        args.difficulty = "beginner"
        args.issue_type = None
        args.limit = 100
        args.format = "text"
        args.verbose = False

        cmd_list(args)

        captured = capsys.readouterr()
        assert "Beginner" in captured.out or "beginner" in captured.out.lower()


class TestStatsWorkflow:
    """Tests for statistics workflow."""

    def test_stats_workflow(self, test_db, multiple_issues_in_db, capsys):
        """Test statistics command."""
        args = Mock()
        cmd_stats(args)

        captured = capsys.readouterr()
        assert (
            "Total Issues" in captured.out
            or "total_issues" in captured.out.lower()
            or "issues" in captured.out.lower()
        )
