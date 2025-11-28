"""
Tests for ML training and prediction functionality.
"""
import os
import pickle
from unittest.mock import patch

import numpy as np
import pytest
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

from contribution_matcher.scoring import extract_features, load_labeled_issues, predict_issue_quality, train_model


class TestExtractFeatures:
    """Tests for feature extraction."""
    
    def test_extract_features_with_profile(self, test_db, sample_profile, sample_issue_in_db):
        """Test extracting features when profile is available."""
        from contribution_matcher.database import query_issues
        
        issues = query_issues()
        issue = issues[0]
        
        features = extract_features(issue, sample_profile)
        
        assert len(features) == 15  # Should have 15 features
        assert all(isinstance(f, (int, float)) for f in features)
        
        # Feature 1: Number of technologies
        assert features[0] >= 0
        
        # Features 2-8: Profile match scores (should be non-zero with profile)
        assert any(f > 0 for f in features[1:8])
    
    def test_extract_features_without_profile(self, test_db, sample_issue_in_db):
        """Test extracting features when profile is missing."""
        from contribution_matcher.database import query_issues
        
        issues = query_issues()
        issue = issues[0]
        
        features = extract_features(issue, None)
        
        assert len(features) == 15
        
        # Features 2-8 should be 0.0 without profile
        assert all(f == 0.0 for f in features[1:8])
        
        # Other features should still be populated
        assert features[0] >= 0  # Technology count
        assert features[8] >= 0  # Repo stars
    
    def test_extract_features_issue_type_encoding(self, test_db, sample_profile):
        """Test that issue types are properly encoded."""
        from contribution_matcher.database import upsert_issue
        
        # Create issues with different types
        bug_id = upsert_issue(
            title="Bug",
            url="https://github.com/test/repo/issues/1",
            issue_type="bug",
        )
        feature_id = upsert_issue(
            title="Feature",
            url="https://github.com/test/repo/issues/2",
            issue_type="feature",
        )
        
        from contribution_matcher.database import query_issues
        issues = query_issues()
        bug_issue = [i for i in issues if i["id"] == bug_id][0]
        feature_issue = [i for i in issues if i["id"] == feature_id][0]
        
        bug_features = extract_features(bug_issue, sample_profile)
        feature_features = extract_features(feature_issue, sample_profile)
        
        # Feature 12 is issue type encoding
        assert bug_features[11] == 1.0  # bug = 1.0
        assert feature_features[11] == 2.0  # feature = 2.0
    
    def test_extract_features_difficulty_encoding(self, test_db, sample_profile):
        """Test that difficulty levels are properly encoded."""
        from contribution_matcher.database import upsert_issue
        
        beginner_id = upsert_issue(
            title="Beginner",
            url="https://github.com/test/repo/issues/1",
            difficulty="beginner",
        )
        advanced_id = upsert_issue(
            title="Advanced",
            url="https://github.com/test/repo/issues/2",
            difficulty="advanced",
        )
        
        from contribution_matcher.database import query_issues
        issues = query_issues()
        beginner_issue = [i for i in issues if i["id"] == beginner_id][0]
        advanced_issue = [i for i in issues if i["id"] == advanced_id][0]
        
        beginner_features = extract_features(beginner_issue, sample_profile)
        advanced_features = extract_features(advanced_issue, sample_profile)
        
        # Feature 13 is difficulty encoding
        assert beginner_features[12] == 0.0  # beginner = 0.0
        assert advanced_features[12] == 2.0  # advanced = 2.0
    
    def test_extract_features_time_estimate_parsing(self, test_db, sample_profile):
        """Test that time estimates are properly parsed to hours."""
        from contribution_matcher.database import upsert_issue
        
        hour_issue_id = upsert_issue(
            title="Hour task",
            url="https://github.com/test/repo/issues/1",
            time_estimate="5 hours",
        )
        day_issue_id = upsert_issue(
            title="Day task",
            url="https://github.com/test/repo/issues/2",
            time_estimate="2 days",
        )
        
        from contribution_matcher.database import query_issues
        issues = query_issues()
        hour_issue = [i for i in issues if i["id"] == hour_issue_id][0]
        day_issue = [i for i in issues if i["id"] == day_issue_id][0]
        
        hour_features = extract_features(hour_issue, sample_profile)
        day_features = extract_features(day_issue, sample_profile)
        
        # Feature 14 is time estimate in hours
        assert hour_features[13] == 5.0
        assert day_features[13] == 16.0  # 2 days * 8 hours


class TestLoadLabeledIssues:
    """Tests for loading labeled issues."""
    
    def test_load_labeled_issues(self, test_db, labeled_issues_for_ml):
        """Test loading labeled issues from database."""
        issues, labels = load_labeled_issues()
        
        assert len(issues) == 2
        assert len(labels) == 2
        assert "good" in labels
        assert "bad" in labels
    
    def test_load_labeled_issues_empty(self, test_db):
        """Test loading when no labeled issues exist."""
        issues, labels = load_labeled_issues()
        
        assert len(issues) == 0
        assert len(labels) == 0


class TestTrainModel:
    """Tests for ML model training."""
    
    def test_train_model_minimum_samples(self, test_db, labeled_issues_for_ml):
        """Test training with minimum required samples."""
        # Create more labeled issues to meet minimum
        from contribution_matcher.database import upsert_issue, update_issue_label
        from contribution_matcher.database import query_issues
        
        # Add more good and bad labels to reach 10 minimum
        for i in range(8):  # Already have 2, need 8 more
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i+20}",
                body="Test",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)
        
        # Train with force flag (since we have < 200)
        results = train_model(force=True)
        
        assert "accuracy" in results
        assert "precision" in results
        assert "recall" in results
        assert "f1_score" in results
        assert 0 <= results["accuracy"] <= 1
        
        # Verify model files were created
        assert os.path.exists("issue_classifier.pkl")
        assert os.path.exists("issue_scaler.pkl")
        
        # Cleanup
        if os.path.exists("issue_classifier.pkl"):
            os.remove("issue_classifier.pkl")
        if os.path.exists("issue_scaler.pkl"):
            os.remove("issue_scaler.pkl")
    
    def test_train_model_insufficient_samples(self, test_db):
        """Test training fails with insufficient samples."""
        # Create only 5 labeled issues (below minimum of 10)
        from contribution_matcher.database import upsert_issue, update_issue_label
        
        for i in range(5):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i}",
                body="Test",
            )
            update_issue_label(issue_id, "good" if i % 2 == 0 else "bad")
        
        with pytest.raises(ValueError, match="Not enough labeled issues"):
            train_model()
    
    def test_train_model_only_one_class(self, test_db):
        """Test training fails when only one label class exists."""
        from contribution_matcher.database import upsert_issue, update_issue_label
        
        # Create 10 issues, all labeled "good"
        for i in range(10):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i}",
                body="Test",
            )
            update_issue_label(issue_id, "good")
        
        with pytest.raises(ValueError, match="Need both 'good' and 'bad' labels"):
            train_model(force=True)
    
    def test_train_model_without_profile(self, test_db, labeled_issues_for_ml):
        """Test training works without profile data."""
        # Remove profile if it exists
        if os.path.exists("dev_profile.json"):
            os.rename("dev_profile.json", "dev_profile.json.bak")
        
        try:
            # Add more labels
            from contribution_matcher.database import upsert_issue, update_issue_label
            
            for i in range(8):
                issue_id = upsert_issue(
                    title=f"Test Issue {i}",
                    url=f"https://github.com/test/repo/issues/{i+20}",
                    body="Test",
                    difficulty="intermediate",
                    issue_type="bug",
                    repo_stars=100,
                )
                label = "good" if i % 2 == 0 else "bad"
                update_issue_label(issue_id, label)
            
            results = train_model(force=True)
            
            assert "accuracy" in results
            # Features 2-8 should be 0.0 without profile, but model should still train
            
            # Cleanup
            if os.path.exists("issue_classifier.pkl"):
                os.remove("issue_classifier.pkl")
            if os.path.exists("issue_scaler.pkl"):
                os.remove("issue_scaler.pkl")
        finally:
            # Restore profile
            if os.path.exists("dev_profile.json.bak"):
                os.rename("dev_profile.json.bak", "dev_profile.json")


class TestPredictIssueQuality:
    """Tests for issue quality prediction."""
    
    def test_predict_without_model(self, test_db, sample_profile, sample_issue_in_db):
        """Test prediction when no model exists."""
        from contribution_matcher.database import query_issues
        
        issues = query_issues()
        issue = issues[0]
        
        good_prob, bad_prob = predict_issue_quality(issue, sample_profile)
        
        # Should return neutral prediction
        assert good_prob == 0.5
        assert bad_prob == 0.5
    
    def test_predict_with_model(self, test_db, labeled_issues_for_ml, sample_profile):
        """Test prediction with trained model."""
        # Train model first
        from contribution_matcher.database import upsert_issue, update_issue_label
        
        # Add more labels to meet minimum
        for i in range(8):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i+20}",
                body="Test",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)
        
        train_model(force=True)
        
        try:
            # Create a test issue
            from contribution_matcher.database import upsert_issue
            from contribution_matcher.database import query_issues
            
            test_issue_id = upsert_issue(
                title="Test Prediction",
                url="https://github.com/test/repo/issues/100",
                body="Python Django issue",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=150,
            )
            
            issues = query_issues()
            test_issue = [i for i in issues if i["id"] == test_issue_id][0]
            
            good_prob, bad_prob = predict_issue_quality(test_issue, sample_profile)
            
            assert 0 <= good_prob <= 1
            assert 0 <= bad_prob <= 1
            assert abs(good_prob + bad_prob - 1.0) < 0.01  # Should sum to ~1
        finally:
            # Cleanup
            if os.path.exists("issue_classifier.pkl"):
                os.remove("issue_classifier.pkl")
            if os.path.exists("issue_scaler.pkl"):
                os.remove("issue_scaler.pkl")

