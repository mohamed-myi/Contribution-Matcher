"""ML Training Module for Issue Quality Prediction."""

import os
import pickle
import re

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import SelectKBest, mutual_info_classif
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import TimeSeriesSplit, train_test_split
from sklearn.preprocessing import StandardScaler

from core.profile import load_dev_profile


def _get_issue_technologies_orm(issue_id: int, session) -> list[tuple[str, str | None]]:
    """Get technologies for an issue using ORM."""
    from core.models import IssueTechnology

    results = session.query(IssueTechnology).filter(IssueTechnology.issue_id == issue_id).all()
    return [(r.technology, r.technology_category) for r in results]


MODEL_PATH_V2 = "issue_classifier_v2_xgb.pkl"
SCALER_PATH_V2 = "issue_scaler_v2.pkl"
FEATURE_SELECTOR_PATH_V2 = "feature_selector_v2.pkl"
MODEL_PATH = "issue_classifier.pkl"
SCALER_PATH = "issue_scaler.pkl"


def extract_base_features(
    issue: dict, profile_data: dict | None = None, session=None
) -> list[float]:
    """Extract base numerical features from an issue (14 features)."""

    from core.scoring.issue_scorer import get_match_breakdown

    features: list[float] = []
    issue_id = issue.get("id")
    if issue_id and session:
        # Ensure issue_id is an integer (handle case where it might be a string)
        try:
            issue_id_int = int(issue_id) if not isinstance(issue_id, int) else issue_id
            issue_techs_tuples = _get_issue_technologies_orm(issue_id_int, session)
            all_issue_technologies = [tech for tech, _ in issue_techs_tuples]
        except (ValueError, TypeError):
            all_issue_technologies = []
    else:
        all_issue_technologies = []

    features.append(len(all_issue_technologies))

    if profile_data:
        try:
            breakdown = get_match_breakdown(profile_data, issue, session=session)
            skills = breakdown.get("skills", {})
            features.append(skills.get("match_percentage", 0.0))
            exp = breakdown.get("experience", {})
            features.append(exp.get("score", 0.0))
            repo_quality = breakdown.get("repo_quality", {})
            features.append(repo_quality.get("score", 0.0))
            freshness = breakdown.get("freshness", {})
            features.append(freshness.get("score", 0.0))
            time_match = breakdown.get("time_match", {})
            features.append(time_match.get("score", 0.0))
            interest_match = breakdown.get("interest_match", {})
            features.append(interest_match.get("score", 0.0))
            from core.constants import (
                SKILL_MATCH_WEIGHT,
            )

            skill_score = (skills.get("match_percentage", 0.0) / 100.0) * SKILL_MATCH_WEIGHT
            rule_based_score = (
                skill_score
                + exp.get("score", 0.0)
                + repo_quality.get("score", 0.0)
                + freshness.get("score", 0.0)
                + time_match.get("score", 0.0)
                + interest_match.get("score", 0.0)
            )
            features.append(rule_based_score)

        except Exception:
            features.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    else:
        features.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

    features.append(float(issue.get("repo_stars") or 0))
    features.append(float(issue.get("repo_forks") or 0))
    features.append(float(issue.get("contributor_count") or 0))

    issue_type = issue.get("issue_type", "") or ""
    type_map = {
        "bug": 1.0,
        "feature": 2.0,
        "documentation": 3.0,
        "testing": 4.0,
        "refactoring": 5.0,
    }
    features.append(type_map.get(issue_type.lower() if issue_type else "", 0.0))

    difficulty = issue.get("difficulty", "") or ""
    difficulty_map = {"beginner": 0.0, "intermediate": 1.0, "advanced": 2.0}
    features.append(difficulty_map.get(difficulty.lower() if difficulty else "", 1.0))
    time_estimate = issue.get("time_estimate", "")
    hours_estimate = 0.0
    if time_estimate:
        hour_match = re.search(
            r"(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)", time_estimate.lower()
        )
        if hour_match:
            if hour_match.group(2):
                hours_estimate = (int(hour_match.group(1)) + int(hour_match.group(2))) / 2
            else:
                hours_estimate = float(hour_match.group(1))
        else:
            day_match = re.search(r"(\d+)\s*(?:-\s*(\d+))?\s*(?:day|days)", time_estimate.lower())
            if day_match:
                if day_match.group(2):
                    days = (int(day_match.group(1)) + int(day_match.group(2))) / 2
                else:
                    days = int(day_match.group(1))
                hours_estimate = days * 8
            elif "weekend" in time_estimate.lower():
                hours_estimate = 16.0
            elif "small" in time_estimate.lower() or "quick" in time_estimate.lower():
                hours_estimate = 2.0
    features.append(hours_estimate)

    return features


def extract_features(
    issue: dict, profile_data: dict | None = None, use_advanced: bool = True, session=None
) -> list[float]:
    """
    Extract numerical features from an issue for ML training.

    Combines base features (14) with optional advanced features (embeddings and
    engineered values) for a total of 207 features when enabled.

    Args:
        issue: Issue dictionary from the database.
        profile_data: Optional profile data for calculating match scores.
        use_advanced: Include advanced features when True.
        session: Optional SQLAlchemy session for database queries.

    Returns:
        List of feature values (14 or 207 items).
    """

    # Extract base features (11)
    base_features = extract_base_features(issue, profile_data, session=session)

    if not use_advanced:
        return base_features

    # Extract advanced features (196)
    try:
        from core.scoring.feature_extractor import extract_advanced_features

        advanced_features = extract_advanced_features(
            issue, profile_data, base_features, use_embeddings=True, session=session
        )
        return base_features + advanced_features
    except ImportError:
        # Fallback if feature_extractor not available
        return base_features


def load_labeled_issues(session=None) -> tuple[list[dict], list[str]]:
    """
    Load labeled issues from the database.

    Args:
        session: Optional SQLAlchemy session. If not provided, creates one.

    Returns:
        Tuple of (issues, labels) where labels are normalized strings.
    """
    from core.models import Issue

    close_session = False
    if session is None:
        from core.db import db

        db.initialize()
        session = db.get_session()
        close_session = True

    try:
        results = (
            session.query(Issue)
            .filter(
                Issue.label.isnot(None),
                Issue.label != "",
                Issue.label.in_(["good", "bad"]),
            )
            .all()
        )

        issues = []
        labels = []
        for issue in results:
            issue_dict = issue.to_dict()
            issues.append(issue_dict)
            labels.append(issue.label.lower())

        return issues, labels
    finally:
        if close_session:
            session.close()


def optimize_hyperparameters(X_train, y_train, tune_iterations: int = 50) -> dict:
    """
    Optimize XGBoost hyperparameters using Bayesian optimization.

    Args:
        X_train: Training feature matrix.
        y_train: Training labels.
        tune_iterations: Number of optimization iterations.

    Returns:
        Dictionary of tuned hyperparameters.
    """
    try:
        import xgboost as xgb
        from skopt import gp_minimize
        from skopt.space import Integer, Real
        from skopt.utils import use_named_args
    except ImportError:
        raise ImportError(
            "XGBoost and scikit-optimize are required for hyperparameter optimization. "
            "Install with: pip install xgboost scikit-optimize"
        )

    # Define search space
    space = [
        Integer(50, 300, name="n_estimators"),
        Integer(3, 7, name="max_depth"),
        Real(0.01, 0.2, name="learning_rate"),
        Real(0.6, 1.0, name="subsample"),
        Real(0.6, 1.0, name="colsample_bytree"),
        Real(0.0, 1.0, name="reg_alpha"),
        Real(0.0, 2.0, name="reg_lambda"),
    ]

    # Objective function (maximize recall)
    @use_named_args(dimensions=space)
    def objective(**params):
        model = xgb.XGBClassifier(
            **params,
            random_state=42,
            eval_metric="logloss",
            use_label_encoder=False,
        )

        # Use time series split for validation
        tscv = TimeSeriesSplit(n_splits=3)
        scores = []
        for train_idx, val_idx in tscv.split(X_train):
            X_tr, X_val = X_train[train_idx], X_train[val_idx]
            y_tr, y_val = y_train[train_idx], y_train[val_idx]

            model.fit(X_tr, y_tr)
            y_pred = model.predict(X_val)
            recall = recall_score(y_val, y_pred)
            scores.append(recall)

        # Return negative recall (minimize = maximize recall)
        return -np.mean(scores)

    # Run optimization
    result = gp_minimize(
        func=objective,
        dimensions=space,
        n_calls=tune_iterations,
        random_state=42,
        n_jobs=-1,
    )

    # Extract best parameters
    best_params = {
        "n_estimators": result.x[0],
        "max_depth": result.x[1],
        "learning_rate": result.x[2],
        "subsample": result.x[3],
        "colsample_bytree": result.x[4],
        "reg_alpha": result.x[5],
        "reg_lambda": result.x[6],
    }

    return best_params


def find_optimal_threshold(model, X_val, y_val) -> float:
    """
    Select the decision threshold that maximizes F1 score.

    Args:
        model: Trained classifier with predict_proba.
        X_val: Validation feature matrix.
        y_val: Validation labels.

    Returns:
        Threshold value that maximizes F1 on validation data.
    """
    y_pred_proba = model.predict_proba(X_val)[:, 1]

    best_threshold = 0.5
    best_f1 = 0.0

    for threshold in np.arange(0.1, 0.9, 0.05):
        y_pred = (y_pred_proba >= threshold).astype(int)
        f1 = f1_score(y_val, y_pred)
        if f1 > best_f1:
            best_f1 = f1
            best_threshold = threshold

    return best_threshold


def train_xgboost_model(
    X_train,
    y_train,
    X_test,
    y_test,
    use_stacking: bool = True,
    use_tuning: bool = True,
    tune_iterations: int = 50,
) -> tuple:
    """
    Train an XGBoost-based model with optional stacking and tuning.

    Args:
        X_train: Training features.
        y_train: Training labels.
        X_test: Test features.
        y_test: Test labels.
        use_stacking: Enable stacking ensemble when True.
        use_tuning: Enable hyperparameter optimization when True.
        tune_iterations: Number of tuning iterations.

    Returns:
        Tuple of (trained model, optimal threshold, metrics dictionary).
    """
    try:
        import xgboost as xgb
        from lightgbm import LGBMClassifier
        from sklearn.ensemble import StackingClassifier
    except ImportError:
        raise ImportError(
            "XGBoost and LightGBM are required for advanced training. "
            "Install with: pip install xgboost lightgbm"
        )

    # Handle class imbalance
    good_count = np.sum(y_train == 1)
    bad_count = np.sum(y_train == 0)
    scale_pos_weight = bad_count / good_count if good_count > 0 else 1.0

    if use_tuning:
        print("Optimizing hyperparameters...")
        best_params = optimize_hyperparameters(X_train, y_train, tune_iterations)
        print(f"Best parameters: {best_params}")
    else:
        # Default parameters
        best_params = {
            "n_estimators": 100,
            "max_depth": 5,
            "learning_rate": 0.1,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 1.0,
        }

    if use_stacking:
        # Create base models
        base_models = [
            (
                "xgb",
                xgb.XGBClassifier(
                    **best_params,
                    random_state=42,
                    scale_pos_weight=scale_pos_weight,
                    eval_metric="logloss",
                    use_label_encoder=False,
                ),
            ),
            (
                "lgbm",
                LGBMClassifier(
                    n_estimators=best_params["n_estimators"],
                    max_depth=best_params["max_depth"],
                    learning_rate=best_params["learning_rate"],
                    subsample=best_params["subsample"],
                    colsample_bytree=best_params["colsample_bytree"],
                    reg_alpha=best_params["reg_alpha"],
                    reg_lambda=best_params["reg_lambda"],
                    random_state=42,
                    scale_pos_weight=scale_pos_weight,
                    verbose=-1,
                ),
            ),
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=best_params["max_depth"],
                    random_state=42,
                    class_weight="balanced",
                    n_jobs=-1,
                ),
            ),
        ]

        # Meta-learner
        meta_learner = xgb.XGBClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            random_state=42,
            eval_metric="logloss",
            use_label_encoder=False,
        )

        # Create stacking ensemble
        model = StackingClassifier(
            estimators=base_models,
            final_estimator=meta_learner,
            cv=3,
            n_jobs=-1,
        )
    else:
        # Single XGBoost model
        model = xgb.XGBClassifier(
            **best_params,
            random_state=42,
            scale_pos_weight=scale_pos_weight,
            eval_metric="logloss",
            use_label_encoder=False,
        )

    # Train model
    print("Training model...")
    model.fit(X_train, y_train)

    # Find optimal threshold
    print("Finding optimal threshold...")
    threshold = find_optimal_threshold(model, X_test, y_test)
    print(f"Optimal threshold: {threshold:.3f}")

    # Evaluate
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    y_pred = (y_pred_proba >= threshold).astype(int)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    metrics = {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "threshold": threshold,
    }

    return model, threshold, metrics


def train_legacy_model(force: bool = False) -> dict:
    """
    Train the legacy GradientBoosting model implementation.

    Args:
        force: Train even when labeled data is below the recommended threshold.

    Returns:
        Dictionary containing training metrics and metadata.
    """

    print("\n" + "=" * 80)
    print("STEP 1: LOADING LABELED ISSUES")
    print("=" * 80)

    issues, labels = load_labeled_issues()
    print(f"Found {len(issues)} labeled issues in database")

    print("\n" + "=" * 80)
    print("STEP 2: VALIDATING DATA REQUIREMENTS")
    print("=" * 80)

    if len(issues) < 10:
        raise ValueError(
            f"Not enough labeled issues ({len(issues)}). Need at least 10 to train.\n"
            "Label more issues using: python main.py label-export"
        )

    if not force and len(issues) < 200:
        raise ValueError(
            f"Only {len(issues)} labeled issues. Minimum recommended is 200 for good accuracy.\n"
            "Use --force to train anyway (model may be less accurate).\n"
            "Label more issues using: python main.py label-export"
        )

    good_count = labels.count("good")
    bad_count = labels.count("bad")

    if good_count == 0 or bad_count == 0:
        raise ValueError(
            "Need both 'good' and 'bad' labels to train. Currently have: "
            f"good={good_count}, bad={bad_count}\n"
            "Label some issues as 'bad' to teach the model what to avoid."
        )

    print("Data validation passed:")
    print(f"  - Total issues: {len(issues)}")
    print(f"  - Good issues: {good_count}")
    print(f"  - Bad issues: {bad_count}")
    print(f"  - Balance: {min(good_count, bad_count) / max(good_count, bad_count) * 100:.1f}%")

    print("\n" + "=" * 80)
    print("STEP 3: LOADING PROFILE DATA")
    print("=" * 80)

    profile_data = None
    try:
        profile_data = load_dev_profile()
        print("Profile data loaded - will calculate match scores (features 2-8)")
    except FileNotFoundError:
        print("Warning: Profile data not found (dev_profile.json)")
        print("  Match score features (2-8) will be 0.0")
    except Exception as e:
        print(f"Warning: Error loading profile data: {e}")

    print("\n" + "=" * 80)
    print("STEP 4: EXTRACTING FEATURES")
    print("=" * 80)

    X = []
    y = []

    for issue, label in zip(issues, labels, strict=False):
        try:
            features = extract_features(issue, profile_data, use_advanced=False)
            X.append(features)
            y.append(1 if label == "good" else 0)
        except Exception as e:
            print(f"Warning: Error extracting features for issue {issue.get('id')}: {e}")
            continue

    if len(X) < 10:
        raise ValueError(
            f"Not enough valid feature vectors ({len(X)}). Need at least 10.\n"
            "Some issues may have missing data. Check your database."
        )

    X = np.array(X)
    y = np.array(y)

    print("Feature extraction complete:")
    print(f"  - Issues processed: {len(X)}")
    print(f"  - Features per issue: {X.shape[1]} (should be 11)")

    print("\n" + "=" * 80)
    print("STEP 5: SPLITTING DATA INTO TRAIN/TEST SETS")
    print("=" * 80)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    print("Data split complete:")
    print(f"  - Training set: {len(X_train)} issues (80%)")
    print(f"  - Test set: {len(X_test)} issues (20%)")

    print("\n" + "=" * 80)
    print("STEP 6: SCALING FEATURES")
    print("=" * 80)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print("Feature scaling complete")

    print("\n" + "=" * 80)
    print("STEP 7: TRAINING GRADIENT BOOSTING CLASSIFIER")
    print("=" * 80)

    model = GradientBoostingClassifier(
        n_estimators=100, learning_rate=0.1, max_depth=5, random_state=42
    )

    model.fit(X_train_scaled, y_train)

    print("Model training complete")

    print("\n" + "=" * 80)
    print("STEP 8: EVALUATING MODEL PERFORMANCE")
    print("=" * 80)

    y_pred = model.predict(X_test_scaled)
    model.predict_proba(X_test_scaled)

    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)

    print(f"\nACCURACY: {accuracy:.3f} ({accuracy * 100:.1f}%)")
    print(f"PRECISION: {precision:.3f} ({precision * 100:.1f}%)")
    print(f"RECALL: {recall:.3f} ({recall * 100:.1f}%)")
    print(f"F1-SCORE: {f1:.3f} ({f1 * 100:.1f}%)")

    cm = confusion_matrix(y_test, y_pred)
    print("\nCONFUSION MATRIX:")
    print("                Predicted")
    print("              Bad    Good")
    print(f"Actual Bad   {cm[0][0]:4d}   {cm[0][1]:4d}")
    print(f"       Good  {cm[1][0]:4d}   {cm[1][1]:4d}")

    print("\n" + "=" * 80)
    print("STEP 9: SAVING MODEL AND SCALER")
    print("=" * 80)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"Model saved to {MODEL_PATH}")

    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Scaler saved to {SCALER_PATH}")

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "confusion_matrix": cm.tolist(),
        "num_samples": len(X),
        "train_size": len(X_train),
        "test_size": len(X_test),
    }


def train_model(
    force: bool = False,
    use_advanced: bool = True,
    use_stacking: bool = True,
    use_tuning: bool = True,
    tune_iterations: int = 50,
    legacy: bool = False,
) -> dict:
    """
    Train the ML model to predict issue quality (good vs bad).

    Args:
        force: Train even with low labeled data counts.
        use_advanced: Include advanced feature set when True.
        use_stacking: Use stacking ensemble when True.
        use_tuning: Run hyperparameter tuning when True.
        tune_iterations: Number of tuning iterations.
        legacy: Train the legacy model instead of v2 when True.

    Returns:
        Dictionary containing evaluation metrics and artifacts metadata.
    """

    if legacy:
        return train_legacy_model(force=force)

    print("\n" + "=" * 80)
    print("STEP 1: LOADING LABELED ISSUES")
    print("=" * 80)

    issues, labels = load_labeled_issues()
    print(f"Found {len(issues)} labeled issues in database")

    print("\n" + "=" * 80)
    print("STEP 2: VALIDATING DATA REQUIREMENTS")
    print("=" * 80)

    if len(issues) < 10:
        raise ValueError(
            f"Not enough labeled issues ({len(issues)}). Need at least 10 to train.\n"
            "Label more issues using: python main.py label-export"
        )

    if not force and len(issues) < 200:
        raise ValueError(
            f"Only {len(issues)} labeled issues. Minimum recommended is 200 for good accuracy.\n"
            "Use --force to train anyway (model may be less accurate).\n"
            "Label more issues using: python main.py label-export"
        )

    good_count = labels.count("good")
    bad_count = labels.count("bad")

    if good_count == 0 or bad_count == 0:
        raise ValueError(
            "Need both 'good' and 'bad' labels to train. Currently have: "
            f"good={good_count}, bad={bad_count}\n"
            "Label some issues as 'bad' to teach the model what to avoid."
        )

    print("Data validation passed:")
    print(f"  - Total issues: {len(issues)}")
    print(f"  - Good issues: {good_count}")
    print(f"  - Bad issues: {bad_count}")
    print(f"  - Balance: {min(good_count, bad_count) / max(good_count, bad_count) * 100:.1f}%")

    print("\n" + "=" * 80)
    print("STEP 3: LOADING PROFILE DATA")
    print("=" * 80)

    profile_data = None
    try:
        profile_data = load_dev_profile()
        print("Profile data loaded")
    except FileNotFoundError:
        print("Warning: Profile data not found")
    except Exception as e:
        print(f"Warning: Error loading profile data: {e}")

    print("\n" + "=" * 80)
    print("STEP 4: EXTRACTING FEATURES")
    print("=" * 80)

    X = []
    y = []

    for issue, label in zip(issues, labels, strict=False):
        try:
            features = extract_features(issue, profile_data, use_advanced=use_advanced)
            X.append(features)
            y.append(1 if label == "good" else 0)
        except Exception as e:
            print(f"Warning: Error extracting features for issue {issue.get('id')}: {e}")
            continue

    if len(X) < 10:
        raise ValueError(
            f"Not enough valid feature vectors ({len(X)}). Need at least 10.\n"
            "Some issues may have missing data. Check your database."
        )

    X = np.array(X)
    y = np.array(y)

    expected_features = 207 if use_advanced else 14
    print("Feature extraction complete:")
    print(f"  - Issues processed: {len(X)}")
    print(f"  - Features per issue: {X.shape[1]} (expected: {expected_features})")

    print("\n" + "=" * 80)
    print("STEP 5: SPLITTING DATA (TIME SERIES)")
    print("=" * 80)

    tscv = TimeSeriesSplit(n_splits=5)
    splits = list(tscv.split(X))
    train_idx, test_idx = splits[-1]

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    print("Data split complete (time series):")
    print(f"  - Training set: {len(X_train)} issues")
    print(f"  - Test set: {len(X_test)} issues")

    print("\n" + "=" * 80)
    print("STEP 6: FEATURE SELECTION")
    print("=" * 80)

    # Select top 100 features using mutual information
    feature_selector = SelectKBest(score_func=mutual_info_classif, k=min(100, X_train.shape[1]))
    X_train_selected = feature_selector.fit_transform(X_train, y_train)
    X_test_selected = feature_selector.transform(X_test)

    print("Feature selection complete:")
    print(f"  - Selected {X_train_selected.shape[1]} features from {X_train.shape[1]} total")

    print("\n" + "=" * 80)
    print("STEP 7: SCALING FEATURES")
    print("=" * 80)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train_selected)
    X_test_scaled = scaler.transform(X_test_selected)

    print("Feature scaling complete")

    print("\n" + "=" * 80)
    print("STEP 8: TRAINING XGBOOST MODEL")
    print("=" * 80)

    model, threshold, metrics = train_xgboost_model(
        X_train_scaled,
        y_train,
        X_test_scaled,
        y_test,
        use_stacking=use_stacking,
        use_tuning=use_tuning,
        tune_iterations=tune_iterations,
    )

    print("\n" + "=" * 80)
    print("STEP 9: EVALUATING MODEL PERFORMANCE")
    print("=" * 80)

    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    y_pred = (y_pred_proba >= threshold).astype(int)

    cm = confusion_matrix(y_test, y_pred)
    print("\nCONFUSION MATRIX:")
    print("                Predicted")
    print("              Bad    Good")
    print(f"Actual Bad   {cm[0][0]:4d}   {cm[0][1]:4d}")
    print(f"       Good  {cm[1][0]:4d}   {cm[1][1]:4d}")

    print("\n" + "=" * 80)
    print("STEP 10: SAVING MODEL AND ARTIFACTS")
    print("=" * 80)

    with open(MODEL_PATH_V2, "wb") as f:
        pickle.dump(model, f)
    print(f"Model saved to {MODEL_PATH_V2}")

    with open(SCALER_PATH_V2, "wb") as f:
        pickle.dump(scaler, f)
    print(f"Scaler saved to {SCALER_PATH_V2}")

    with open(FEATURE_SELECTOR_PATH_V2, "wb") as f:
        pickle.dump(feature_selector, f)
    print(f"Feature selector saved to {FEATURE_SELECTOR_PATH_V2}")

    print("\n" + "=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)

    return {
        "accuracy": metrics["accuracy"],
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1_score": metrics["f1_score"],
        "threshold": metrics["threshold"],
        "confusion_matrix": cm.tolist(),
        "num_samples": len(X),
        "train_size": len(X_train),
        "test_size": len(X_test),
    }


def predict_issue_quality(issue: dict, profile_data: dict | None = None) -> tuple[float, float]:
    """
    Predict whether an issue is good or bad using the trained model.

    Auto-detects the available model version (v2 or legacy) and applies the
    corresponding feature pipeline.

    Args:
        issue: Issue dictionary from the database.
        profile_data: Optional profile data for feature extraction.

    Returns:
        Tuple of (probability_good, probability_bad).
    """

    # Try to load version 2 model first
    if (
        os.path.exists(MODEL_PATH_V2)
        and os.path.exists(SCALER_PATH_V2)
        and os.path.exists(FEATURE_SELECTOR_PATH_V2)
    ):
        try:
            with open(MODEL_PATH_V2, "rb") as f:
                model = pickle.load(f)
            with open(SCALER_PATH_V2, "rb") as f:
                scaler = pickle.load(f)
            with open(FEATURE_SELECTOR_PATH_V2, "rb") as f:
                feature_selector = pickle.load(f)

            # Extract features (with advanced features)
            features = extract_features(issue, profile_data, use_advanced=True)
            X = np.array([features])

            # Apply feature selection
            X_selected = feature_selector.transform(X)

            # Scale features
            X_scaled = scaler.transform(X_selected)

            # Predict
            proba = model.predict_proba(X_scaled)[0]
            return proba[1], proba[0]  # (good_prob, bad_prob)

        except Exception as e:
            print(f"Warning: Error loading v2 model: {e}")
            # Fall through to legacy model

    # Fall back to legacy model
    if os.path.exists(MODEL_PATH) and os.path.exists(SCALER_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                model = pickle.load(f)
            with open(SCALER_PATH, "rb") as f:
                scaler = pickle.load(f)

            # Extract features (base only for legacy)
            features = extract_features(issue, profile_data, use_advanced=False)
            X = np.array([features])
            X_scaled = scaler.transform(X)

            proba = model.predict_proba(X_scaled)[0]
            return proba[1], proba[0]  # (good_prob, bad_prob)

        except Exception as e:
            print(f"Warning: Error in ML prediction: {e}")
            return 0.5, 0.5  # Neutral prediction

    # No model found
    return 0.5, 0.5  # Neutral prediction
