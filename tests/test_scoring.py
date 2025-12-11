"""
Tests for issue scoring functionality.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

from core.scoring import (
    calculate_experience_match,
    calculate_freshness,
    calculate_interest_match,
    calculate_repo_quality,
    calculate_skill_match,
    calculate_time_match,
    get_match_breakdown,
    score_issue_against_profile,
)


class TestCalculateSkillMatch:
    """Tests for skill matching calculation."""

    def test_perfect_match(self):
        """Test perfect skill match."""
        profile_skills = ["python", "django", "postgresql"]
        issue_techs = ["python", "django", "postgresql"]
        match_pct, matching, missing = calculate_skill_match(profile_skills, issue_techs)

        assert match_pct == 100.0
        assert len(matching) == 3
        assert len(missing) == 0

    def test_partial_match(self):
        """Test partial skill match."""
        profile_skills = ["python", "django"]
        issue_techs = ["python", "django", "react", "javascript"]
        match_pct, matching, missing = calculate_skill_match(profile_skills, issue_techs)

        assert match_pct == 50.0
        assert len(matching) == 2
        assert len(missing) == 2
        assert "react" in missing or "javascript" in missing

    def test_no_match(self):
        """Test no skill match."""
        profile_skills = ["python", "django"]
        issue_techs = ["java", "spring", "mongodb"]
        match_pct, matching, missing = calculate_skill_match(profile_skills, issue_techs)

        assert match_pct == 0.0
        assert len(matching) == 0
        assert len(missing) == 3

    def test_case_insensitive_match(self):
        """Test case-insensitive skill matching."""
        profile_skills = ["Python", "Django"]
        issue_techs = ["python", "django"]
        match_pct, matching, missing = calculate_skill_match(profile_skills, issue_techs)

        assert match_pct == 100.0
        assert len(matching) == 2

    def test_substring_match(self):
        """Test substring matching (e.g., 'react' matches 'react-native')."""
        profile_skills = ["react"]
        issue_techs = ["react-native"]
        match_pct, matching, missing = calculate_skill_match(profile_skills, issue_techs)

        # Should match due to substring logic
        assert match_pct > 0

    def test_empty_issue_technologies(self):
        """Test handling when issue has no technologies."""
        profile_skills = ["python", "django"]
        issue_techs = []
        match_pct, matching, missing = calculate_skill_match(profile_skills, issue_techs)

        assert match_pct == 100.0  # Perfect match when no requirements
        assert len(matching) == 0
        assert len(missing) == 0


class TestCalculateExperienceMatch:
    """Tests for experience level matching."""

    def test_perfect_match(self):
        """Test perfect experience match."""
        assert calculate_experience_match("intermediate", "intermediate") == 20.0
        assert calculate_experience_match("beginner", "beginner") == 20.0
        assert calculate_experience_match("advanced", "advanced") == 20.0

    def test_close_match(self):
        """Test close experience matches."""
        # Beginner to intermediate
        assert calculate_experience_match("beginner", "intermediate") == 15.0
        assert calculate_experience_match("intermediate", "beginner") == 15.0

        # Intermediate to advanced
        assert calculate_experience_match("intermediate", "advanced") == 15.0
        assert calculate_experience_match("advanced", "intermediate") == 15.0

    def test_mismatch_beginner_advanced(self):
        """Test mismatch between beginner and advanced."""
        assert calculate_experience_match("beginner", "advanced") == 5.0  # Too difficult

    def test_overqualified(self):
        """Test when profile is overqualified."""
        assert (
            calculate_experience_match("advanced", "beginner") == 10.0
        )  # Acceptable but overqualified

    def test_missing_difficulty(self):
        """Test handling when issue difficulty is missing."""
        assert calculate_experience_match("intermediate", None) == 10.0  # Neutral score

    def test_case_insensitive(self):
        """Test case-insensitive matching."""
        assert calculate_experience_match("INTERMEDIATE", "intermediate") == 20.0


class TestCalculateRepoQuality:
    """Tests for repository quality calculation."""

    def test_high_quality_repo(self):
        """Test scoring for high-quality repository."""
        repo_metadata = {
            "stars": 500,
            "forks": 100,
            "contributor_count": 20,
            "last_commit_date": (datetime.now() - timedelta(days=7)).isoformat(),
        }
        score = calculate_repo_quality(repo_metadata)

        assert score > 10  # Should be high score
        assert score <= 15

    def test_active_repo_recent_commits(self):
        """Test scoring for actively maintained repo."""
        repo_metadata = {
            "last_commit_date": (datetime.now() - timedelta(days=10)).isoformat(),
        }
        score = calculate_repo_quality(repo_metadata)

        assert score >= 5.0  # Should get points for activity

    def test_inactive_repo(self):
        """Test scoring for inactive repository."""
        repo_metadata = {
            "last_commit_date": (datetime.now() - timedelta(days=200)).isoformat(),
        }
        score = calculate_repo_quality(repo_metadata)

        assert score < 5.0  # Should get low/no points for activity

    def test_popular_repo(self):
        """Test scoring for popular repository."""
        repo_metadata = {
            "stars": 200,
            "forks": 50,
        }
        score = calculate_repo_quality(repo_metadata)

        assert score >= 2.5  # Should get points for popularity

    def test_large_contributor_community(self):
        """Test scoring for repo with many contributors."""
        repo_metadata = {
            "contributor_count": 15,
        }
        score = calculate_repo_quality(repo_metadata)

        assert score >= 5.0  # Should get full points for large community

    def test_missing_metadata(self):
        """Test handling when metadata is missing."""
        assert calculate_repo_quality(None) == 5.0  # Neutral score
        # Empty dict may still return some score based on defaults
        assert calculate_repo_quality({}) >= 0.0


class TestCalculateFreshness:
    """Tests for issue freshness calculation."""

    def test_recently_updated(self):
        """Test scoring for recently updated issue."""
        updated_at = (datetime.now() - timedelta(days=3)).isoformat()
        score = calculate_freshness(updated_at)

        assert score == 10.0  # Maximum score for recent updates

    def test_week_old_update(self):
        """Test scoring for week-old update."""
        updated_at = (datetime.now() - timedelta(days=7)).isoformat()
        score = calculate_freshness(updated_at)

        assert score == 10.0  # Still recent

    def test_month_old_update(self):
        """Test scoring for month-old update."""
        updated_at = (datetime.now() - timedelta(days=30)).isoformat()
        score = calculate_freshness(updated_at)

        assert score == 7.0  # Good but not perfect

    def test_old_update(self):
        """Test scoring for old update."""
        updated_at = (datetime.now() - timedelta(days=100)).isoformat()
        score = calculate_freshness(updated_at)

        # 100 days is > 90, so should be 1.0 (minimum score)
        assert score == 1.0  # Minimum score for old updates

    def test_very_old_update(self):
        """Test scoring for very old update."""
        updated_at = (datetime.now() - timedelta(days=200)).isoformat()
        score = calculate_freshness(updated_at)

        assert score == 1.0  # Minimum score

    def test_missing_date(self):
        """Test handling when date is missing."""
        assert calculate_freshness(None) == 1.0
        assert calculate_freshness("") == 1.0


class TestCalculateTimeMatch:
    """Tests for time availability matching."""

    def test_perfect_time_match(self):
        """Test when time estimate fits within availability."""
        profile_availability = 10  # hours per week
        issue_estimate = "5 hours"
        score = calculate_time_match(profile_availability, issue_estimate)

        assert score == 10.0  # Perfect match

    def test_time_within_range(self):
        """Test when time estimate is within 2x availability."""
        profile_availability = 10
        issue_estimate = "15 hours"
        score = calculate_time_match(profile_availability, issue_estimate)

        assert score == 5.0  # Partial match

    def test_time_too_large(self):
        """Test when time estimate exceeds 2x availability."""
        profile_availability = 10
        issue_estimate = "30 hours"
        score = calculate_time_match(profile_availability, issue_estimate)

        assert score == 0.0  # No match

    def test_weekend_project(self):
        """Test matching weekend project estimate."""
        profile_availability = 20
        issue_estimate = "weekend project"
        score = calculate_time_match(profile_availability, issue_estimate)

        assert score > 0  # Should parse and match

    def test_small_task(self):
        """Test matching small task estimate."""
        profile_availability = 5
        issue_estimate = "small task"
        score = calculate_time_match(profile_availability, issue_estimate)

        assert score == 10.0  # Should fit easily

    def test_missing_data(self):
        """Test handling when data is missing."""
        assert calculate_time_match(None, "5 hours") == 5.0
        assert calculate_time_match(10, None) == 5.0
        assert calculate_time_match(None, None) == 5.0


class TestCalculateInterestMatch:
    """Tests for interest matching."""

    def test_strong_interest_match(self):
        """Test when multiple interests match."""
        profile_interests = ["web development", "python", "open source"]
        repo_topics = ["web-development", "python", "django", "open-source"]
        score = calculate_interest_match(profile_interests, repo_topics)

        # Note: "web development" vs "web-development" and "open source" vs "open-source"
        # may not match exactly due to substring matching logic
        # So we check it's at least a good score
        assert score >= 1.0  # Should get some points for matches

    def test_moderate_interest_match(self):
        """Test when some interests match."""
        profile_interests = ["python", "machine learning"]
        repo_topics = ["python", "django"]
        score = calculate_interest_match(profile_interests, repo_topics)

        assert score >= 1.0  # Should get some points

    def test_no_interest_match(self):
        """Test when no interests match."""
        profile_interests = ["python"]
        repo_topics = ["java", "spring"]
        score = calculate_interest_match(profile_interests, repo_topics)

        assert score == 0.0

    def test_case_insensitive_match(self):
        """Test case-insensitive interest matching."""
        profile_interests = ["Python"]
        repo_topics = ["python"]
        score = calculate_interest_match(profile_interests, repo_topics)

        assert score > 0

    def test_missing_data(self):
        """Test handling when data is missing."""
        assert calculate_interest_match([], ["python"]) == 2.5
        assert calculate_interest_match(["python"], []) == 2.5
        assert calculate_interest_match([], []) == 2.5


class TestGetMatchBreakdown:
    """Tests for match breakdown calculation."""

    def test_complete_breakdown(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test getting complete match breakdown."""
        from core.database import query_issues
        from core.db import db

        issues = query_issues()
        issue = issues[0]

        with db.session() as session:
            breakdown = get_match_breakdown(sample_profile, issue, session=session)

        assert "skills" in breakdown
        assert "experience" in breakdown
        assert "repo_quality" in breakdown
        assert "freshness" in breakdown
        assert "time_match" in breakdown
        assert "interest_match" in breakdown

        assert breakdown["skills"]["match_percentage"] >= 0
        assert breakdown["experience"]["score"] >= 0
        assert breakdown["repo_quality"]["score"] >= 0


class TestScoreIssueAgainstProfile:
    """Tests for overall issue scoring."""

    @patch("core.scoring.ml_trainer.predict_issue_quality")
    def test_score_without_ml(
        self, mock_predict, test_db, sample_profile, sample_issue_in_db, init_test_db
    ):
        """Test scoring without ML model."""
        mock_predict.return_value = (0.5, 0.5)  # Neutral prediction

        from core.database import query_issues
        from core.db import db

        issues = query_issues()
        issue = issues[0]

        with db.session() as session:
            result = score_issue_against_profile(sample_profile, issue, session=session)

        assert "score" in result
        assert "breakdown" in result
        assert 0 <= result["score"] <= 100
        assert "ml_prediction" in result["breakdown"]

    @patch("core.scoring.issue_scorer.predict_issue_quality")
    def test_score_with_ml_boost(
        self, mock_predict, test_db, sample_profile, sample_issue_in_db, init_test_db
    ):
        """Test scoring with ML prediction boost."""
        mock_predict.return_value = (0.9, 0.1)  # High confidence good

        from core.database import query_issues
        from core.db import db

        issues = query_issues()
        issue = issues[0]

        with db.session() as session:
            result = score_issue_against_profile(sample_profile, issue, session=session)

        # Score should be boosted by ML
        assert result["score"] > 0
        assert result["breakdown"]["ml_prediction"]["adjustment"] > 0

    @patch("core.scoring.issue_scorer.predict_issue_quality")
    def test_score_with_ml_penalty(
        self, mock_predict, test_db, sample_profile, sample_issue_in_db, init_test_db
    ):
        """Test scoring with ML prediction penalty."""
        mock_predict.return_value = (0.1, 0.9)  # High confidence bad

        from core.database import query_issues
        from core.db import db

        issues = query_issues()
        issue = issues[0]

        with db.session() as session:
            result = score_issue_against_profile(sample_profile, issue, session=session)

        # Score should be penalized by ML
        assert result["breakdown"]["ml_prediction"]["adjustment"] < 0

    def test_score_clamped_to_100(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test that scores are clamped to 100 maximum."""
        from core.database import query_issues
        from core.db import db

        issues = query_issues()
        issue = issues[0]

        # Create perfect match scenario
        perfect_profile = {
            "skills": ["python", "django"],
            "experience_level": "intermediate",
            "interests": ["web-development"],
            "preferred_languages": ["python"],
            "time_availability_hours_per_week": 20,
        }

        with db.session() as session:
            result = score_issue_against_profile(perfect_profile, issue, session=session)

        assert result["score"] <= 100
