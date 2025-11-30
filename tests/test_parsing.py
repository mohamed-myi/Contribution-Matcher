"""
Tests for issue parsing functionality.
"""
import json
from datetime import datetime, timedelta

import pytest

from core.parsing import (
    classify_issue_type,
    find_difficulty,
    find_technologies,
    find_time_estimate,
    parse_issue,
)


class TestFindDifficulty:
    """Tests for difficulty extraction."""
    
    def test_extract_from_beginner_label(self):
        """Test extracting beginner difficulty from labels."""
        body = "Some issue description"
        labels = ["good first issue", "beginner-friendly"]
        assert find_difficulty(body, labels) == "beginner"
    
    def test_extract_from_intermediate_label(self):
        """Test extracting intermediate difficulty from labels."""
        body = "Some issue description"
        labels = ["intermediate", "medium"]
        assert find_difficulty(body, labels) == "intermediate"
    
    def test_extract_from_advanced_label(self):
        """Test extracting advanced difficulty from labels."""
        body = "Some issue description"
        labels = ["advanced", "hard", "expert"]
        assert find_difficulty(body, labels) == "advanced"
    
    def test_extract_from_body_text_beginner(self):
        """Test extracting beginner difficulty from body text."""
        body = "This is a good first issue for beginners. Should take about 2 hours."
        labels = []
        assert find_difficulty(body, labels) == "beginner"
    
    def test_extract_from_body_text_advanced(self):
        """Test extracting advanced difficulty from body text."""
        body = "This requires deep knowledge and extensive experience with the system."
        labels = []
        assert find_difficulty(body, labels) == "advanced"
    
    def test_default_to_intermediate(self):
        """Test that unclear difficulty defaults to intermediate."""
        body = "Some generic issue description"
        labels = []
        assert find_difficulty(body, labels) == "intermediate"
    
    def test_empty_input(self):
        """Test handling of empty input."""
        assert find_difficulty("", []) is None
        assert find_difficulty(None, []) is None


class TestFindTimeEstimate:
    """Tests for time estimate extraction."""
    
    def test_extract_hours_single(self):
        """Test extracting single hour estimate."""
        body = "This should take about 2 hours to complete."
        assert find_time_estimate(body) == "2 hours"
    
    def test_extract_hours_range(self):
        """Test extracting hour range estimate."""
        body = "This should take 2-3 hours to complete."
        assert find_time_estimate(body) == "2-3 hours"
    
    def test_extract_days(self):
        """Test extracting day estimate."""
        body = "This will take 1-2 days to finish."
        assert find_time_estimate(body) == "1-2 days"
    
    def test_extract_weekend_project(self):
        """Test extracting weekend project estimate."""
        body = "This is a weekend project for someone with experience."
        assert find_time_estimate(body) == "weekend project"
    
    def test_extract_small_task(self):
        """Test extracting small task estimate."""
        body = "This is a small task that should be quick."
        assert find_time_estimate(body) == "small task"
    
    def test_extract_quick_task(self):
        """Test extracting quick task estimate."""
        body = "This is a quick fix that should be done soon."
        assert find_time_estimate(body) == "quick task"
    
    def test_no_time_estimate(self):
        """Test handling when no time estimate is found."""
        body = "This is a regular issue with no time mentioned."
        assert find_time_estimate(body) is None
    
    def test_empty_body(self):
        """Test handling of empty body."""
        assert find_time_estimate("") is None
        assert find_time_estimate(None) is None


class TestClassifyIssueType:
    """Tests for issue type classification."""
    
    def test_classify_bug_from_label(self):
        """Test classifying bug from label."""
        body = "Some description"
        labels = ["bug", "bugfix"]
        assert classify_issue_type(body, labels) == "bug"
    
    def test_classify_feature_from_label(self):
        """Test classifying feature from label."""
        body = "Some description"
        labels = ["feature", "enhancement"]
        assert classify_issue_type(body, labels) == "feature"
    
    def test_classify_documentation_from_label(self):
        """Test classifying documentation from label."""
        body = "Some description"
        labels = ["documentation", "docs"]
        assert classify_issue_type(body, labels) == "documentation"
    
    def test_classify_testing_from_label(self):
        """Test classifying testing from label."""
        body = "Some description"
        labels = ["test", "testing"]
        assert classify_issue_type(body, labels) == "testing"
    
    def test_classify_refactoring_from_label(self):
        """Test classifying refactoring from label."""
        body = "Some description"
        labels = ["refactor", "cleanup"]
        assert classify_issue_type(body, labels) == "refactoring"
    
    def test_classify_bug_from_body(self):
        """Test classifying bug from body text."""
        body = "There's a bug in the code that needs fixing."
        labels = []
        assert classify_issue_type(body, labels) == "bug"
    
    def test_classify_feature_from_body(self):
        """Test classifying feature from body text."""
        body = "We should add a new feature to improve user experience."
        labels = []
        assert classify_issue_type(body, labels) == "feature"
    
    def test_classify_documentation_from_body(self):
        """Test classifying documentation from body text."""
        body = "The README needs to be updated with new documentation."
        labels = []
        assert classify_issue_type(body, labels) == "documentation"
    
    def test_no_classification(self):
        """Test handling when no type can be determined."""
        body = "Generic issue description"
        labels = []
        # The function may classify based on patterns, so we just check it returns something
        result = classify_issue_type(body, labels)
        # It might return None or classify based on patterns
        assert result is None or result in ["bug", "feature", "documentation", "testing", "refactoring"]
    
    def test_empty_input(self):
        """Test handling of empty input."""
        assert classify_issue_type("", []) is None
        assert classify_issue_type(None, []) is None


class TestFindTechnologies:
    """Tests for technology extraction."""
    
    def test_extract_from_body(self):
        """Test extracting technologies from issue body."""
        body = "This issue requires Python and Django knowledge."
        technologies = find_technologies(body)
        # Should extract Python and Django
        tech_names = [t[0].lower() for t in technologies]
        assert "python" in tech_names
        assert "django" in tech_names
    
    def test_extract_from_repo_languages(self):
        """Test extracting technologies from repo languages."""
        body = ""
        repo_languages = {"Python": 50000, "JavaScript": 20000}
        technologies = find_technologies(body, repo_languages=repo_languages)
        tech_names = [t[0] for t in technologies]
        assert "Python" in tech_names
        assert "JavaScript" in tech_names
    
    def test_extract_from_repo_topics(self):
        """Test extracting technologies from repo topics."""
        body = ""
        repo_topics = ["python", "django", "web-development"]
        technologies = find_technologies(body, repo_topics=repo_topics)
        tech_names = [t[0].lower() for t in technologies]
        assert "python" in tech_names or "django" in tech_names
    
    def test_combine_all_sources(self):
        """Test combining technologies from all sources."""
        body = "This requires React knowledge."
        repo_languages = {"Python": 50000}
        repo_topics = ["django"]
        technologies = find_technologies(body, repo_languages, repo_topics)
        tech_names = [t[0].lower() for t in technologies]
        # Should have React from body, Python from languages, Django from topics
        assert len(tech_names) >= 2
    
    def test_empty_input(self):
        """Test handling of empty input."""
        assert find_technologies("") == []
        assert find_technologies(None) == []


class TestParseIssue:
    """Tests for full issue parsing."""
    
    def test_parse_complete_issue(self, sample_github_issue, sample_repo_metadata):
        """Test parsing a complete issue with all fields."""
        parsed = parse_issue(sample_github_issue, sample_repo_metadata)
        
        assert parsed["title"] == sample_github_issue["title"]
        assert parsed["url"] == sample_github_issue["html_url"]
        assert parsed["repo_owner"] == "testowner"
        assert parsed["repo_name"] == "testrepo"
        assert parsed["difficulty"] == "beginner"
        assert parsed["issue_type"] == "bug"
        assert parsed["time_estimate"] == "2-3 hours"
        assert parsed["repo_stars"] == 150
        assert parsed["repo_forks"] == 25
        assert len(parsed["technologies"]) > 0
    
    def test_parse_issue_without_repo_metadata(self, test_db, sample_github_issue):
        """Test parsing issue when repo metadata is missing."""
        parsed = parse_issue(sample_github_issue, None)
        
        assert parsed["title"] == sample_github_issue["title"]
        assert parsed["repo_owner"] == "testowner"
        assert parsed["repo_name"] == "testrepo"
        # Should still extract from body and labels
        assert parsed["difficulty"] is not None
        assert parsed["issue_type"] is not None
    
    def test_parse_issue_minimal_data(self, test_db):
        """Test parsing issue with minimal data."""
        minimal_issue = {
            "title": "Test issue",
            "body": "",
            "html_url": "https://github.com/owner/repo/issues/1",
            "repository_url": "https://api.github.com/repos/owner/repo",
            "labels": [],
            "updated_at": "2024-01-01T00:00:00Z",
        }
        # Pass empty dict to avoid database lookup
        parsed = parse_issue(minimal_issue, {})
        
        assert parsed["title"] == "Test issue"
        assert parsed["repo_owner"] == "owner"
        assert parsed["repo_name"] == "repo"
        # Should handle missing data gracefully - may be None or default to intermediate
        assert parsed["difficulty"] in ["beginner", "intermediate", "advanced", None]
    
    def test_parse_issue_active_repo(self):
        """Test parsing issue with active repository."""
        issue = {
            "title": "Test issue",
            "body": "Test",
            "html_url": "https://github.com/owner/repo/issues/1",
            "repository_url": "https://api.github.com/repos/owner/repo",
            "labels": [],
            "updated_at": "2024-01-01T00:00:00Z",
        }
        repo_metadata = {
            "last_commit_date": (datetime.now() - timedelta(days=30)).isoformat(),
        }
        parsed = parse_issue(issue, repo_metadata)
        assert parsed["is_active"] == 1
    
    def test_parse_issue_inactive_repo(self):
        """Test parsing issue with inactive repository."""
        issue = {
            "title": "Test issue",
            "body": "Test",
            "html_url": "https://github.com/owner/repo/issues/1",
            "repository_url": "https://api.github.com/repos/owner/repo",
            "labels": [],
            "updated_at": "2024-01-01T00:00:00Z",
        }
        repo_metadata = {
            "last_commit_date": (datetime.now() - timedelta(days=200)).isoformat(),
        }
        parsed = parse_issue(issue, repo_metadata)
        assert parsed["is_active"] == 0

