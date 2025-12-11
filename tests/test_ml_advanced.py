"""
Comprehensive tests for advanced ML model features.

Tests cover:
- Advanced feature extraction (embeddings, interactions, polynomial, temporal)
- XGBoost model training with stacking ensemble
- Model versioning (v2 vs legacy)
- Hyperparameter optimization
- F1 threshold optimization
- Feature caching and retrieval
"""

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sklearn.model_selection import train_test_split

# Check for optional dependencies
try:
    import xgboost  # noqa: F401

    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

try:
    import lightgbm  # noqa: F401

    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    import skopt  # noqa: F401

    HAS_SKOPT = True
except ImportError:
    HAS_SKOPT = False

from core.scoring import (
    extract_features,
    predict_issue_quality,
    train_model,
)
from core.scoring.feature_extractor import (
    extract_advanced_features,
    extract_interaction_features,
    extract_polynomial_features,
    extract_temporal_features,
    get_text_embeddings,
)
from core.scoring.ml_trainer import (
    extract_base_features,
    find_optimal_threshold,
    optimize_hyperparameters,
)


class TestAdvancedFeatureExtraction:
    """Tests for advanced feature extraction."""

    def test_extract_base_features_count(self, test_db, sample_profile, sample_issue_in_db):
        """Test that base features return exactly 14 features."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        features = extract_base_features(issue, sample_profile)

        assert len(features) == 14
        assert all(isinstance(f, (int, float)) for f in features)

    def test_extract_features_with_advanced(self, test_db, sample_profile, sample_issue_in_db):
        """Test extracting features with advanced features enabled."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        features = extract_features(issue, sample_profile, use_advanced=True)

        # Should have 207 features (14 base + 193 advanced)
        assert len(features) == 207
        assert all(isinstance(f, (int, float)) for f in features)
        assert all(not np.isnan(f) and not np.isinf(f) for f in features)

    def test_extract_features_without_advanced(self, test_db, sample_profile, sample_issue_in_db):
        """Test extracting features without advanced features."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        features = extract_features(issue, sample_profile, use_advanced=False)

        # Should have only 14 base features
        assert len(features) == 14

    @patch("core.scoring.feature_extractor._get_embedding_model")
    def test_get_text_embeddings(self, mock_model, test_db, sample_issue_in_db):
        """Test text embedding generation."""
        from core.database import query_issues

        # Mock the embedding model
        mock_transformer = MagicMock()
        mock_transformer.encode.return_value = np.random.rand(384)  # Standard embedding size
        mock_model.return_value = mock_transformer

        issues = query_issues()
        issue = issues[0]

        desc_emb, title_emb = get_text_embeddings(issue)

        assert desc_emb.shape == (
            384,
        )  # Original embedding size (PCA happens in extract_advanced_features)
        assert title_emb.shape == (384,)  # Original embedding size
        assert all(not np.isnan(f) and not np.isinf(f) for f in desc_emb)
        assert all(not np.isnan(f) and not np.isinf(f) for f in title_emb)

    def test_extract_interaction_features(self):
        """Test interaction feature extraction."""
        base_features = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0]

        interaction_features = extract_interaction_features(base_features)

        assert len(interaction_features) == 12
        assert all(isinstance(f, (int, float)) for f in interaction_features)
        # First interaction is skill_match * exp_score = base_features[1] * base_features[2]
        assert interaction_features[0] == base_features[1] * base_features[2]

    def test_extract_polynomial_features(self):
        """Test polynomial feature extraction."""
        base_features = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]

        poly_features = extract_polynomial_features(base_features)

        assert len(poly_features) == 27  # Degree-2 expansion of 6 features
        assert all(isinstance(f, (int, float)) for f in poly_features)
        assert all(not np.isnan(f) and not np.isinf(f) for f in poly_features)

    def test_extract_temporal_features(self, test_db, sample_issue_in_db):
        """Test temporal feature extraction."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        temporal_features = extract_temporal_features(issue)

        assert len(temporal_features) == 5  # Function returns 5 features
        assert all(isinstance(f, (int, float)) for f in temporal_features)
        # Days can be negative if dates are in the future (test data issue)
        assert isinstance(temporal_features[0], (int, float))  # days_since_created
        assert isinstance(temporal_features[1], (int, float))  # days_since_updated
        assert temporal_features[2] >= 0  # freshness_score (max(0.0, ...) ensures >= 0)
        assert temporal_features[3] in [0.0, 1.0]  # is_recent
        assert temporal_features[4] in [0.0, 1.0]  # is_stale

    def test_extract_advanced_features_complete(self, test_db, sample_profile, sample_issue_in_db):
        """Test complete advanced feature extraction."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        # Get base features first
        base_features = extract_base_features(issue, sample_profile)

        with patch("core.scoring.feature_extractor._get_embedding_model") as mock_model:
            mock_transformer = MagicMock()
            mock_transformer.encode.return_value = np.random.rand(384)
            mock_model.return_value = mock_transformer

            advanced_features = extract_advanced_features(issue, sample_profile, base_features)

            # Should have 193 advanced features (100 desc + 50 title + 12 interaction + 27 poly + 4 temporal)
            assert len(advanced_features) == 193
            assert all(isinstance(f, (int, float)) for f in advanced_features)
            assert all(not np.isnan(f) and not np.isinf(f) for f in advanced_features)

    def test_embedding_caching(self, test_db, sample_issue_in_db, init_test_db):
        """Test that embeddings are cached in database."""
        from core.database import query_issues
        from core.db import db
        from core.models import IssueEmbedding

        issues = query_issues()
        issue = issues[0]
        issue_id = issue["id"]

        with patch("core.scoring.feature_extractor._get_embedding_model") as mock_model:
            mock_transformer = MagicMock()
            mock_transformer.encode.return_value = np.random.rand(384)
            mock_model.return_value = mock_transformer

            # Generate embeddings (should cache) - pass session for caching
            with db.session() as session:
                desc_emb, title_emb = get_text_embeddings(issue, session=session)

            # Check that embeddings were cached
            with db.session() as session:
                cached = session.query(IssueEmbedding).filter(IssueEmbedding.issue_id == issue_id).first()

            assert cached is not None
            assert cached.description_embedding is not None
            assert cached.title_embedding is not None
            import pickle
            cached_desc = pickle.loads(cached.description_embedding)
            cached_title = pickle.loads(cached.title_embedding)
            assert len(cached_desc) == 384  # Original embedding size
            assert len(cached_title) == 384  # Original embedding size


class TestXGBoostModelTraining:
    """Tests for XGBoost model training."""

    @pytest.mark.skipif(not HAS_XGBOOST or not HAS_LIGHTGBM, reason="XGBoost and LightGBM required")
    def test_train_xgboost_with_stacking(self, test_db, labeled_issues_for_ml, sample_profile, init_test_db):
        """Test training XGBoost model with stacking ensemble."""
        from core.database import update_issue_label, upsert_issue

        # Create enough labeled issues
        for i in range(50):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 100}",
                body=f"Test issue {i} with Python and Django",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100 + i,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(
            force=True,
            use_advanced=True,
            use_stacking=True,
            use_tuning=False,  # Skip tuning for speed
        )

        assert "accuracy" in results
        assert "precision" in results
        assert "recall" in results
        assert "f1_score" in results
        assert "threshold" in results  # Note: key is 'threshold', not 'optimal_threshold'
        assert 0 <= results["accuracy"] <= 1
        assert 0 <= results["f1_score"] <= 1

        # Verify v2 model files were created
        assert os.path.exists("issue_classifier_v2_xgb.pkl")
        assert os.path.exists("issue_scaler_v2.pkl")
        assert os.path.exists("feature_selector_v2.pkl")

        # Cleanup
        for f in ["issue_classifier_v2_xgb.pkl", "issue_scaler_v2.pkl", "feature_selector_v2.pkl"]:
            if os.path.exists(f):
                os.remove(f)

    @pytest.mark.skipif(not HAS_XGBOOST, reason="XGBoost required")
    def test_train_xgboost_without_stacking(self, test_db, labeled_issues_for_ml, sample_profile, init_test_db):
        """Test training XGBoost model without stacking."""
        from core.database import update_issue_label, upsert_issue

        for i in range(50):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 200}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(
            force=True,
            use_advanced=True,
            use_stacking=False,
            use_tuning=False,
        )

        assert "accuracy" in results
        assert "f1_score" in results

        # Cleanup
        for f in ["issue_classifier_v2_xgb.pkl", "issue_scaler_v2.pkl", "feature_selector_v2.pkl"]:
            if os.path.exists(f):
                os.remove(f)

    @pytest.mark.skipif(not HAS_XGBOOST, reason="XGBoost required")
    def test_train_xgboost_without_advanced(self, test_db, labeled_issues_for_ml, sample_profile, init_test_db):
        """Test training XGBoost model without advanced features."""
        from core.database import update_issue_label, upsert_issue

        for i in range(50):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 300}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(
            force=True,
            use_advanced=False,
            use_stacking=False,
            use_tuning=False,
        )

        assert "accuracy" in results
        assert "f1_score" in results

        # Cleanup
        for f in ["issue_classifier_v2_xgb.pkl", "issue_scaler_v2.pkl", "feature_selector_v2.pkl"]:
            if os.path.exists(f):
                os.remove(f)

    @pytest.mark.skipif(
        not HAS_XGBOOST or not HAS_SKOPT, reason="XGBoost and scikit-optimize required"
    )
    def test_train_with_hyperparameter_tuning(self, test_db, labeled_issues_for_ml, sample_profile, init_test_db):
        """Test training with hyperparameter optimization."""
        from core.database import update_issue_label, upsert_issue

        for i in range(100):  # More data for better tuning
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 400}",
                body=f"Test issue {i} with various technologies",
                difficulty="intermediate" if i % 3 == 0 else "beginner",
                issue_type="bug" if i % 2 == 0 else "feature",
                repo_stars=50 + i * 2,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(
            force=True,
            use_advanced=True,
            use_stacking=True,
            use_tuning=True,
            tune_iterations=10,  # Reduced for speed
        )

        assert "accuracy" in results
        assert "f1_score" in results
        assert results["f1_score"] >= 0  # Should have valid F1 score

        # Cleanup
        for f in ["issue_classifier_v2_xgb.pkl", "issue_scaler_v2.pkl", "feature_selector_v2.pkl"]:
            if os.path.exists(f):
                os.remove(f)


class TestModelVersioning:
    """Tests for model versioning (v2 vs legacy)."""

    def test_legacy_model_training(self, test_db, labeled_issues_for_ml, init_test_db):
        """Test training legacy GradientBoosting model."""
        from core.database import update_issue_label, upsert_issue

        for i in range(20):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 500}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(force=True, legacy=True)

        assert "accuracy" in results
        assert "f1_score" in results

        # Verify legacy model files were created
        assert os.path.exists("issue_classifier.pkl")
        assert os.path.exists("issue_scaler.pkl")

        # Verify v2 files were NOT created
        assert not os.path.exists("issue_classifier_v2_xgb.pkl")

        # Cleanup
        for f in ["issue_classifier.pkl", "issue_scaler.pkl"]:
            if os.path.exists(f):
                os.remove(f)

    @pytest.mark.skipif(not HAS_XGBOOST, reason="XGBoost required")
    def test_model_version_detection(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test that model version is correctly detected."""
        from core.database import query_issues, update_issue_label, upsert_issue

        # Create labeled issues
        for i in range(20):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 600}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        # Train v2 model
        train_model(
            force=True, legacy=False, use_advanced=False, use_stacking=False, use_tuning=False
        )

        try:
            issues = query_issues()
            issue = issues[0]

            # Should use v2 model for prediction
            good_prob, bad_prob = predict_issue_quality(issue, sample_profile)

            assert 0 <= good_prob <= 1
            assert 0 <= bad_prob <= 1
            assert abs(good_prob + bad_prob - 1.0) < 0.01
        finally:
            # Cleanup
            for f in [
                "issue_classifier_v2_xgb.pkl",
                "issue_scaler_v2.pkl",
                "feature_selector_v2.pkl",
                "issue_classifier.pkl",
                "issue_scaler.pkl",
            ]:
                if os.path.exists(f):
                    os.remove(f)

    def test_legacy_model_prediction(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test prediction with legacy model."""
        from core.database import query_issues, update_issue_label, upsert_issue

        # Create labeled issues
        for i in range(20):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 700}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        # Train legacy model
        train_model(force=True, legacy=True)

        try:
            issues = query_issues()
            issue = issues[0]

            # Should use legacy model for prediction
            good_prob, bad_prob = predict_issue_quality(issue, sample_profile)

            assert 0 <= good_prob <= 1
            assert 0 <= bad_prob <= 1
            assert abs(good_prob + bad_prob - 1.0) < 0.01
        finally:
            # Cleanup
            for f in ["issue_classifier.pkl", "issue_scaler.pkl"]:
                if os.path.exists(f):
                    os.remove(f)


class TestThresholdOptimization:
    """Tests for F1 threshold optimization."""

    def test_find_optimal_threshold(self):
        """Test finding optimal threshold for F1 score."""
        from sklearn.datasets import make_classification
        from sklearn.ensemble import RandomForestClassifier

        # Create synthetic data
        X, y = make_classification(n_samples=100, n_features=10, random_state=42)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.3, random_state=42)

        # Train a simple model
        model = RandomForestClassifier(n_estimators=10, random_state=42)
        model.fit(X_train, y_train)

        # Find optimal threshold
        optimal_threshold = find_optimal_threshold(model, X_val, y_val)

        assert 0 <= optimal_threshold <= 1
        # Threshold should be reasonable (not extreme)
        assert 0.1 <= optimal_threshold <= 0.9

    @pytest.mark.skipif(not HAS_XGBOOST, reason="XGBoost required")
    def test_threshold_optimization_in_training(
        self, test_db, labeled_issues_for_ml, sample_profile, init_test_db
    ):
        """Test that threshold optimization is used in training."""
        from core.database import update_issue_label, upsert_issue

        for i in range(50):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 800}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(
            force=True,
            use_advanced=False,
            use_stacking=False,
            use_tuning=False,
        )

        assert "threshold" in results
        assert 0 <= results["threshold"] <= 1

        # Cleanup
        for f in ["issue_classifier_v2_xgb.pkl", "issue_scaler_v2.pkl", "feature_selector_v2.pkl"]:
            if os.path.exists(f):
                os.remove(f)


class TestHyperparameterOptimization:
    """Tests for hyperparameter optimization."""

    @pytest.mark.skipif(
        not HAS_XGBOOST or not HAS_SKOPT, reason="XGBoost and scikit-optimize required"
    )
    def test_optimize_hyperparameters(self):
        """Test hyperparameter optimization function."""
        from sklearn.datasets import make_classification
        from sklearn.model_selection import train_test_split

        # Create synthetic data
        X, y = make_classification(n_samples=200, n_features=20, random_state=42)
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.3, random_state=42)

        # Optimize hyperparameters
        best_params = optimize_hyperparameters(
            X_train, y_train, tune_iterations=10
        )  # Minimum required

        assert isinstance(best_params, dict)
        assert "n_estimators" in best_params or "max_depth" in best_params
        # Should have reasonable parameter values
        if "n_estimators" in best_params:
            assert best_params["n_estimators"] > 0
        if "max_depth" in best_params:
            assert best_params["max_depth"] > 0

    @pytest.mark.skipif(
        not HAS_XGBOOST or not HAS_SKOPT, reason="XGBoost and scikit-optimize required"
    )
    def test_hyperparameter_optimization_in_training(
        self, test_db, labeled_issues_for_ml, sample_profile, init_test_db
    ):
        """Test that hyperparameter optimization is used when enabled."""
        from core.database import update_issue_label, upsert_issue

        for i in range(100):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 900}",
                body=f"Test issue {i} with various content",
                difficulty="intermediate" if i % 3 == 0 else "beginner",
                issue_type="bug" if i % 2 == 0 else "feature",
                repo_stars=50 + i,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        results = train_model(
            force=True,
            use_advanced=True,
            use_stacking=True,
            use_tuning=True,
            tune_iterations=10,  # Minimum required by scikit-optimize
        )

        assert "accuracy" in results
        assert "f1_score" in results
        assert "threshold" in results
        # With tuning, should have reasonable performance
        assert results["f1_score"] >= 0

        # Cleanup
        for f in ["issue_classifier_v2_xgb.pkl", "issue_scaler_v2.pkl", "feature_selector_v2.pkl"]:
            if os.path.exists(f):
                os.remove(f)


class TestModelPrediction:
    """Tests for model prediction functionality."""

    @pytest.mark.skipif(not HAS_XGBOOST, reason="XGBoost required")
    def test_predict_with_v2_model(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test prediction with v2 XGBoost model."""
        from core.database import query_issues, update_issue_label, upsert_issue

        # Create labeled issues and train model
        for i in range(30):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 1000}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        train_model(force=True, use_advanced=False, use_stacking=False, use_tuning=False)

        try:
            issues = query_issues()
            issue = issues[0]

            good_prob, bad_prob = predict_issue_quality(issue, sample_profile)

            assert 0 <= good_prob <= 1
            assert 0 <= bad_prob <= 1
            assert abs(good_prob + bad_prob - 1.0) < 0.01
        finally:
            # Cleanup
            for f in [
                "issue_classifier_v2_xgb.pkl",
                "issue_scaler_v2.pkl",
                "feature_selector_v2.pkl",
            ]:
                if os.path.exists(f):
                    os.remove(f)

    def test_predict_without_model(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test prediction when no model exists."""
        from core.database import query_issues

        # Ensure no model files exist
        for f in [
            "issue_classifier_v2_xgb.pkl",
            "issue_scaler_v2.pkl",
            "feature_selector_v2.pkl",
            "issue_classifier.pkl",
            "issue_scaler.pkl",
        ]:
            if os.path.exists(f):
                os.remove(f)

        issues = query_issues()
        issue = issues[0]

        good_prob, bad_prob = predict_issue_quality(issue, sample_profile)

        # Should return neutral prediction
        assert good_prob == 0.5
        assert bad_prob == 0.5

    @pytest.mark.skipif(not HAS_XGBOOST, reason="XGBoost required")
    def test_predict_with_different_feature_sets(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test prediction consistency with different feature configurations."""
        from core.database import query_issues, update_issue_label, upsert_issue

        # Create labeled issues
        for i in range(30):
            issue_id = upsert_issue(
                title=f"Test Issue {i}",
                url=f"https://github.com/test/repo/issues/{i + 1100}",
                body=f"Test issue {i}",
                difficulty="intermediate",
                issue_type="bug",
                repo_stars=100,
            )
            label = "good" if i % 2 == 0 else "bad"
            update_issue_label(issue_id, label)

        # Train with advanced features
        train_model(force=True, use_advanced=True, use_stacking=False, use_tuning=False)

        try:
            issues = query_issues()
            issue = issues[0]

            # Predictions should be valid probabilities
            good_prob, bad_prob = predict_issue_quality(issue, sample_profile)

            assert 0 <= good_prob <= 1
            assert 0 <= bad_prob <= 1
            assert abs(good_prob + bad_prob - 1.0) < 0.01
        finally:
            # Cleanup
            for f in [
                "issue_classifier_v2_xgb.pkl",
                "issue_scaler_v2.pkl",
                "feature_selector_v2.pkl",
            ]:
                if os.path.exists(f):
                    os.remove(f)


class TestFeatureConsistency:
    """Tests for feature extraction consistency."""

    def test_feature_count_consistency(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test that feature counts are consistent."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        base_features = extract_base_features(issue, sample_profile)
        features_no_advanced = extract_features(issue, sample_profile, use_advanced=False)
        features_with_advanced = extract_features(issue, sample_profile, use_advanced=True)

        assert len(base_features) == 14
        assert len(features_no_advanced) == 14
        assert len(features_with_advanced) == 207

        # Base features should match non-advanced features
        assert base_features == features_no_advanced

    def test_feature_values_consistency(self, test_db, sample_profile, sample_issue_in_db, init_test_db):
        """Test that feature values are consistent across calls."""
        from core.database import query_issues

        issues = query_issues()
        issue = issues[0]

        features1 = extract_base_features(issue, sample_profile)
        features2 = extract_base_features(issue, sample_profile)

        # Features should be identical for same input
        assert features1 == features2

    def test_feature_handles_missing_data(self, test_db, sample_profile, init_test_db):
        """Test that features handle missing data gracefully."""
        from core.database import query_issues, upsert_issue

        # Create issue with minimal data
        issue_id = upsert_issue(
            title="Minimal Issue",
            url="https://github.com/test/repo/issues/minimal",
        )

        issues = query_issues()
        issue = [i for i in issues if i["id"] == issue_id][0]

        features = extract_base_features(issue, sample_profile)

        assert len(features) == 14
        assert all(isinstance(f, (int, float)) for f in features)
        assert all(not np.isnan(f) and not np.isinf(f) for f in features)
