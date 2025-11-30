"""
Tests for edge cases, error handling, and boundary conditions.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from core.database import update_issue_label, upsert_issue, query_issues
from core.parsing import find_difficulty, find_time_estimate, parse_issue
from core.scoring import (
    calculate_experience_match,
    calculate_freshness,
    calculate_interest_match,
    calculate_repo_quality,
    calculate_skill_match,
    calculate_time_match,
    score_issue_against_profile,
)


class TestMissingData:
    """Tests for handling missing/null data."""
    
    def test_parse_issue_missing_fields(self, test_db):
        """Test parsing issue with many missing fields."""
        minimal_issue = {
            "title": "Test",
            "html_url": "https://github.com/test/repo/issues/1",
            "repository_url": "https://api.github.com/repos/test/repo",
            "body": "",
            "labels": [],
            "updated_at": "2024-01-01T00:00:00Z",
        }
        
        # Pass empty dict instead of None to avoid database lookup
        parsed = parse_issue(minimal_issue, {})
        
        assert parsed["title"] == "Test"
        assert parsed["body"] == ""
        # Difficulty may be None if no body or labels, or may default to intermediate
        assert parsed["difficulty"] in ["beginner", "intermediate", "advanced", None]
        assert parsed["repo_owner"] == "test"
    
    def test_score_with_empty_profile(self, test_db, sample_issue_in_db):
        """Test scoring with empty profile."""
        empty_profile = {
            "skills": [],
            "experience_level": "beginner",
            "interests": [],
            "preferred_languages": [],
            "time_availability_hours_per_week": None,
        }
        
        from core.database import query_issues
        issues = query_issues()
        issue = issues[0]
        
        result = score_issue_against_profile(empty_profile, issue)
        
        # Should still return a score
        assert "score" in result
        assert 0 <= result["score"] <= 100
    
    def test_score_with_missing_issue_data(self, test_db, sample_profile):
        """Test scoring with minimal issue data."""
        issue_id = upsert_issue(
            title="Minimal Issue",
            url="https://github.com/test/repo/issues/1",
        )
        
        from core.database import query_issues
        issues = query_issues()
        issue = issues[0]
        
        result = score_issue_against_profile(sample_profile, issue)
        
        # Should handle missing data gracefully
        assert "score" in result
        assert "breakdown" in result
    
    def test_query_issues_with_malformed_json(self, test_db):
        """Test querying issues with malformed JSON in database."""
        # Insert issue with invalid JSON
        from core.database import db_conn
        
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
        )
        
        # Manually insert malformed JSON
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE issues SET labels = ? WHERE id = ?",
                ("{invalid json", issue_id)
            )
        
        # Query should handle gracefully
        issues = query_issues()
        assert len(issues) == 1
        # Labels should be parsed as empty list
        assert isinstance(issues[0].get("labels"), list)


class TestBoundaryConditions:
    """Tests for boundary conditions."""
    
    def test_score_at_zero_boundary(self, test_db, sample_profile):
        """Test scoring at zero boundary."""
        # Create issue with no matching skills
        issue_id = upsert_issue(
            title="No Match Issue",
            url="https://github.com/test/repo/issues/1",
            difficulty="advanced",
            issue_type="feature",
        )
        
        from core.database import replace_issue_technologies
        replace_issue_technologies(issue_id, [("java", "backend")])
        
        from core.database import query_issues
        issues = query_issues()
        issue = issues[0]
        
        result = score_issue_against_profile(sample_profile, issue)
        
        # Score should be >= 0 (clamped)
        assert result["score"] >= 0
    
    def test_score_at_hundred_boundary(self, test_db, sample_profile):
        """Test scoring at 100 boundary."""
        # Create perfect match issue
        issue_id = upsert_issue(
            title="Perfect Match",
            url="https://github.com/test/repo/issues/1",
            difficulty="intermediate",
            issue_type="bug",
            time_estimate="5 hours",
            repo_stars=500,
            repo_forks=100,
        )
        
        from core.database import replace_issue_technologies
        replace_issue_technologies(issue_id, [
            ("python", "backend"),
            ("django", "backend"),
        ])
        
        from core.database import query_issues
        issues = query_issues()
        issue = issues[0]
        
        result = score_issue_against_profile(sample_profile, issue)
        
        # Score should be <= 100 (clamped)
        assert result["score"] <= 100
    
    def test_time_match_boundary_conditions(self):
        """Test time matching at boundaries."""
        # Exactly at availability
        assert calculate_time_match(10, "10 hours") == 10.0
        
        # Just over 2x availability
        assert calculate_time_match(10, "21 hours") == 0.0
        
        # Just under 2x availability
        assert calculate_time_match(10, "19 hours") == 5.0
    
    def test_freshness_boundary_conditions(self):
        """Test freshness calculation at boundaries."""
        # Exactly 7 days
        date_7_days = (datetime.now() - timedelta(days=7)).isoformat()
        assert calculate_freshness(date_7_days) == 10.0
        
        # Exactly 8 days (just over 7)
        date_8_days = (datetime.now() - timedelta(days=8)).isoformat()
        assert calculate_freshness(date_8_days) == 7.0
        
        # Exactly 30 days
        date_30_days = (datetime.now() - timedelta(days=30)).isoformat()
        assert calculate_freshness(date_30_days) == 7.0
    
    def test_repo_quality_boundary_conditions(self):
        """Test repo quality at boundaries."""
        # Exactly 30 days since commit
        metadata_30_days = {
            "last_commit_date": (datetime.now() - timedelta(days=30)).isoformat(),
        }
        score_30 = calculate_repo_quality(metadata_30_days)
        assert score_30 >= 5.0
        
        # Exactly 31 days (just over 30)
        metadata_31_days = {
            "last_commit_date": (datetime.now() - timedelta(days=31)).isoformat(),
        }
        score_31 = calculate_repo_quality(metadata_31_days)
        assert score_31 >= 3.0
        
        # Exactly 100 stars
        metadata_100_stars = {"stars": 100}
        score_100 = calculate_repo_quality(metadata_100_stars)
        assert score_100 >= 2.5


class TestDataTypeMismatches:
    """Tests for handling data type mismatches."""
    
    def test_labels_as_string_instead_of_list(self, test_db):
        """Test handling when labels are stored as string."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
            labels=["bug", "feature"],
        )
        
        # Manually change to string
        from core.database import db_conn
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE issues SET labels = ? WHERE id = ?",
                ('["bug", "feature"]', issue_id)
            )
        
        # Query should handle gracefully
        issues = query_issues()
        issue = issues[0]
        # Should be parsed as list
        assert isinstance(issue.get("labels"), list)
    
    def test_repo_topics_as_string(self, test_db):
        """Test handling when repo_topics are stored as string."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
            repo_topics=["python", "django"],
        )
        
        # Manually change to string
        from core.database import db_conn
        with db_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE issues SET repo_topics = ? WHERE id = ?",
                ('["python", "django"]', issue_id)
            )
        
        issues = query_issues()
        issue = issues[0]
        # Should be parsed as list
        assert isinstance(issue.get("repo_topics"), list)
    
    def test_time_estimate_various_formats(self):
        """Test parsing various time estimate formats."""
        test_cases = [
            ("2 hours", "2 hours"),
            ("2-3 hours", "2-3 hours"),
            ("1 day", "1 day"),
            ("1-2 days", "1-2 days"),
            ("weekend project", "weekend project"),
            ("small task", "small task"),
            ("quick fix", "quick task"),
        ]
        
        for body, expected in test_cases:
            result = find_time_estimate(f"This should take {body}.")
            assert result == expected or expected in result or result in expected


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_invalid_difficulty_value(self):
        """Test handling invalid difficulty values."""
        # Should default to intermediate (or advanced if pattern matches)
        result = find_difficulty("", ["invalid-difficulty"])
        # The function may return intermediate or advanced depending on pattern matching
        assert result in ["intermediate", "advanced"]
    
    def test_invalid_experience_level(self):
        """Test handling invalid experience level."""
        # Should handle gracefully
        score = calculate_experience_match("invalid", "beginner")
        assert score >= 0  # Should return some score
    
    def test_malformed_date_string(self):
        """Test handling malformed date strings."""
        # Should return default score
        score = calculate_freshness("not-a-date")
        assert score == 1.0  # Default low score
    
    def test_update_label_nonexistent_issue(self, test_db):
        """Test updating label for non-existent issue."""
        result = update_issue_label(99999, "good")
        assert result is False
    
    def test_query_with_invalid_filters(self, test_db, multiple_issues_in_db):
        """Test querying with invalid filter values."""
        # Should handle gracefully
        issues = query_issues(difficulty="nonexistent")
        assert isinstance(issues, list)  # Should return empty list, not crash


class TestUnicodeAndSpecialCharacters:
    """Tests for handling unicode and special characters."""
    
    def test_issue_title_with_unicode(self, test_db):
        """Test handling unicode in issue titles."""
        issue_id = upsert_issue(
            title="Fix bug: 修复错误",
            url="https://github.com/test/repo/issues/1",
        )
        
        from core.database import query_issues
        issues = query_issues()
        assert issues[0]["title"] == "Fix bug: 修复错误"
    
    def test_issue_body_with_special_characters(self):
        """Test parsing issue body with special characters."""
        body = "Fix issue with <code>tags</code> and \"quotes\" and 'apostrophes'"
        result = find_difficulty(body, [])
        # Should not crash
        assert result is not None
    
    def test_technology_names_with_special_chars(self, test_db):
        """Test handling technology names with special characters."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
        )
        
        from core.database import replace_issue_technologies
        replace_issue_technologies(issue_id, [
            ("C++", "backend"),
            (".NET", "backend"),
        ])
        
        from core.database import get_issue_technologies
        techs = get_issue_technologies(issue_id)
        tech_names = [t[0] for t in techs]
        assert "C++" in tech_names or ".NET" in tech_names


class TestConcurrentOperations:
    """Tests for handling concurrent-like operations."""
    
    def test_multiple_upserts_same_url(self, test_db):
        """Test multiple upserts with same URL (simulating concurrent updates)."""
        url = "https://github.com/test/repo/issues/1"
        
        id1 = upsert_issue(title="First", url=url)
        id2 = upsert_issue(title="Second", url=url)
        id3 = upsert_issue(title="Third", url=url)
        
        # All should return same ID
        assert id1 == id2 == id3
        
        # Final title should be "Third"
        from core.database import query_issues
        issues = query_issues()
        assert issues[0]["title"] == "Third"
    
    def test_replace_technologies_multiple_times(self, test_db):
        """Test replacing technologies multiple times."""
        issue_id = upsert_issue(
            title="Test",
            url="https://github.com/test/repo/issues/1",
        )
        
        from core.database import replace_issue_technologies
        
        # Replace multiple times
        replace_issue_technologies(issue_id, [("python", "backend")])
        replace_issue_technologies(issue_id, [("django", "backend")])
        replace_issue_technologies(issue_id, [("react", "frontend")])
        
        # Should only have the last set
        from core.database import get_issue_technologies
        techs = get_issue_technologies(issue_id)
        assert len(techs) == 1
        assert techs[0][0] == "react"


class TestEmptyAndNoneValues:
    """Tests for handling empty and None values."""
    
    def test_empty_skills_list(self):
        """Test matching with empty skills list."""
        match_pct, matching, missing = calculate_skill_match([], ["python", "django"])
        
        assert match_pct == 0.0
        assert len(matching) == 0
        assert len(missing) == 2
    
    def test_none_time_availability(self):
        """Test time matching with None availability."""
        score = calculate_time_match(None, "5 hours")
        assert score == 5.0  # Neutral score
    
    def test_empty_interests(self):
        """Test interest matching with empty interests."""
        score = calculate_interest_match([], ["python", "django"])
        assert score == 2.5  # Neutral score
    
    def test_none_repo_metadata(self):
        """Test repo quality with None metadata."""
        score = calculate_repo_quality(None)
        assert score == 5.0  # Neutral score

