"""
ML Training Module for Issue Quality Prediction

This module trains a machine learning model to predict whether a GitHub issue is "good" 
(i.e., an issue you want to contribute to) or "bad" (i.e., an issue you don't want to contribute to).

The model learns from your manual labels - when you label issues as "good" or "bad", 
the model learns patterns from those examples to predict future issues.
"""

import os
import pickle
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

from contribution_matcher.database import db_conn
from contribution_matcher.database import get_issue_technologies
from contribution_matcher.profile import load_dev_profile

# File paths for saving/loading the trained model and feature scaler
MODEL_PATH = "issue_classifier.pkl"
SCALER_PATH = "issue_scaler.pkl"


def extract_features(issue: Dict, profile_data: Optional[Dict] = None) -> List[float]:
    """
    Extract numerical features from an issue for ML training.
    
    This function converts an issue (text/data) into a list of 15 numbers that 
    the ML model can understand. These features focus on ISSUE RELEVANCE - whether the 
    issue matches your skills, experience level, and interests.
    
    Args:
        issue: Issue dictionary from database
        profile_data: Optional profile data for calculating match scores
        
    Returns:
        List of 15 float values representing the issue's features
    """
    # Lazy import to avoid circular dependency
    from contribution_matcher.scoring.issue_scorer import get_match_breakdown, score_issue_against_profile
    
    features = []
    
    # Get issue technologies from database
    issue_id = issue.get('id')
    if issue_id:
        issue_techs_tuples = get_issue_technologies(issue_id)
        all_issue_technologies = [tech for tech, _ in issue_techs_tuples]
    else:
        all_issue_technologies = []
    
    # FEATURE 1: Number of technologies required
    features.append(len(all_issue_technologies))
    
    # FEATURES 2-8: Profile match scores (if profile data available)
    if profile_data:
        try:
            breakdown = get_match_breakdown(profile_data, issue)
            
            # FEATURE 2: Skill match percentage
            skills = breakdown.get('skills', {})
            features.append(skills.get('match_percentage', 0.0))
            
            # FEATURE 3: Experience match score
            exp = breakdown.get('experience', {})
            features.append(exp.get('score', 0.0))
            
            # FEATURE 4: Repo quality score
            repo_quality = breakdown.get('repo_quality', {})
            features.append(repo_quality.get('score', 0.0))
            
            # FEATURE 5: Freshness score
            freshness = breakdown.get('freshness', {})
            features.append(freshness.get('score', 0.0))
            
            # FEATURE 6: Time match score
            time_match = breakdown.get('time_match', {})
            features.append(time_match.get('score', 0.0))
            
            # FEATURE 7: Interest match score
            interest_match = breakdown.get('interest_match', {})
            features.append(interest_match.get('score', 0.0))
            
            # FEATURE 8: Total rule-based score
            score_result = score_issue_against_profile(profile_data, issue)
            features.append(score_result.get('score', 0.0))
            
        except Exception:
            features.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    else:
        features.extend([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    
    # FEATURE 9: Repo stars (normalized)
    repo_stars = issue.get('repo_stars') or 0
    features.append(float(repo_stars))
    
    # FEATURE 10: Repo forks (normalized)
    repo_forks = issue.get('repo_forks') or 0
    features.append(float(repo_forks))
    
    # FEATURE 11: Contributor count (normalized)
    contributor_count = issue.get('contributor_count') or 0
    features.append(float(contributor_count))
    
    # FEATURE 12: Issue type encoded
    issue_type = issue.get('issue_type', '') or ''
    type_map = {
        'bug': 1.0,
        'feature': 2.0,
        'documentation': 3.0,
        'testing': 4.0,
        'refactoring': 5.0,
    }
    features.append(type_map.get(issue_type.lower() if issue_type else '', 0.0))
    
    # FEATURE 13: Difficulty encoded
    difficulty = issue.get('difficulty', '') or ''
    difficulty_map = {
        'beginner': 0.0,
        'intermediate': 1.0,
        'advanced': 2.0,
    }
    features.append(difficulty_map.get(difficulty.lower() if difficulty else '', 1.0))
    
    # FEATURE 14: Time estimate hours
    time_estimate = issue.get('time_estimate', '')
    hours_estimate = 0.0
    if time_estimate:
        import re
        hour_match = re.search(r'(\d+)\s*(?:-\s*(\d+))?\s*(?:hour|hr|hours|hrs)', time_estimate.lower())
        if hour_match:
            if hour_match.group(2):
                hours_estimate = (int(hour_match.group(1)) + int(hour_match.group(2))) / 2
            else:
                hours_estimate = float(hour_match.group(1))
        else:
            day_match = re.search(r'(\d+)\s*(?:-\s*(\d+))?\s*(?:day|days)', time_estimate.lower())
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
    
    # FEATURE 15: Number of labels
    labels = issue.get('labels', [])
    if isinstance(labels, str):
        import json
        try:
            labels = json.loads(labels)
        except (json.JSONDecodeError, TypeError):
            labels = []
    features.append(float(len(labels) if isinstance(labels, list) else 0))
    
    return features


def load_labeled_issues() -> Tuple[List[Dict], List[str]]:
    """
    Load labeled issues from the database.
    
    Returns:
        Tuple of (issues list, labels list)
    """
    with db_conn() as conn:
        cur = conn.cursor()
        
        cur.execute(
            """
            SELECT * FROM issues
            WHERE label IS NOT NULL AND label != ''
            AND label IN ('good', 'bad')
            """
        )
        rows = cur.fetchall()
        
        columns = [description[0] for description in cur.description]
        
        issues = []
        labels = []
        for row in rows:
            issue = dict(zip(columns, row))
            
            # Parse JSON fields
            if issue.get("labels"):
                try:
                    import json
                    issue["labels"] = json.loads(issue["labels"])
                except (json.JSONDecodeError, TypeError):
                    issue["labels"] = []
            
            issues.append(issue)
            labels.append(issue['label'].lower())
    
    return issues, labels


def train_model(force: bool = False) -> Dict:
    """
    Train a machine learning model to predict issue quality (good vs bad).
    
    Args:
        force: If True, train even if you have less than 200 labeled issues
        
    Returns:
        Dictionary with training metrics
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
            "Label more issues using: python contribution_matcher.py label-export"
        )
    
    if not force and len(issues) < 200:
        raise ValueError(
            f"Only {len(issues)} labeled issues. Minimum recommended is 200 for good accuracy.\n"
            "Use --force to train anyway (model may be less accurate).\n"
            "Label more issues using: python contribution_matcher.py label-export"
        )
    
    good_count = labels.count('good')
    bad_count = labels.count('bad')
    
    if good_count == 0 or bad_count == 0:
        raise ValueError(
            "Need both 'good' and 'bad' labels to train. Currently have: "
            f"good={good_count}, bad={bad_count}\n"
            "Label some issues as 'bad' to teach the model what to avoid."
        )
    
    print(f"✓ Data validation passed:")
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
        print("✓ Profile data loaded - will calculate match scores (features 2-8)")
    except FileNotFoundError:
        print("⚠ Warning: Profile data not found (dev_profile.json)")
        print("  Match score features (2-8) will be 0.0")
    except Exception as e:
        print(f"⚠ Warning: Error loading profile data: {e}")
    
    print("\n" + "=" * 80)
    print("STEP 4: EXTRACTING FEATURES")
    print("=" * 80)
    
    X = []
    y = []
    
    for issue, label in zip(issues, labels):
        try:
            features = extract_features(issue, profile_data)
            X.append(features)
            y.append(1 if label == 'good' else 0)
        except Exception as e:
            print(f"⚠ Warning: Error extracting features for issue {issue.get('id')}: {e}")
            continue
    
    if len(X) < 10:
        raise ValueError(
            f"Not enough valid feature vectors ({len(X)}). Need at least 10.\n"
            "Some issues may have missing data. Check your database."
        )
    
    X = np.array(X)
    y = np.array(y)
    
    print(f"✓ Feature extraction complete:")
    print(f"  - Issues processed: {len(X)}")
    print(f"  - Features per issue: {X.shape[1]} (should be 15)")
    
    print("\n" + "=" * 80)
    print("STEP 5: SPLITTING DATA INTO TRAIN/TEST SETS")
    print("=" * 80)
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=42,
        stratify=y
    )
    
    print(f"✓ Data split complete:")
    print(f"  - Training set: {len(X_train)} issues (80%)")
    print(f"  - Test set: {len(X_test)} issues (20%)")
    
    print("\n" + "=" * 80)
    print("STEP 6: SCALING FEATURES")
    print("=" * 80)
    
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("✓ Feature scaling complete")
    
    print("\n" + "=" * 80)
    print("STEP 7: TRAINING GRADIENT BOOSTING CLASSIFIER")
    print("=" * 80)
    
    model = GradientBoostingClassifier(
        n_estimators=100,
        learning_rate=0.1,
        max_depth=5,
        random_state=42
    )
    
    model.fit(X_train_scaled, y_train)
    
    print("✓ Model training complete")
    
    print("\n" + "=" * 80)
    print("STEP 8: EVALUATING MODEL PERFORMANCE")
    print("=" * 80)
    
    y_pred = model.predict(X_test_scaled)
    y_pred_proba = model.predict_proba(X_test_scaled)
    
    accuracy = accuracy_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred)
    
    print(f"\n📊 ACCURACY: {accuracy:.3f} ({accuracy*100:.1f}%)")
    print(f"🎯 PRECISION: {precision:.3f} ({precision*100:.1f}%)")
    print(f"🔍 RECALL: {recall:.3f} ({recall*100:.1f}%)")
    print(f"⚖️  F1-SCORE: {f1:.3f} ({f1*100:.1f}%)")
    
    cm = confusion_matrix(y_test, y_pred)
    print("\nCONFUSION MATRIX:")
    print(f"                Predicted")
    print(f"              Bad    Good")
    print(f"Actual Bad   {cm[0][0]:4d}   {cm[0][1]:4d}")
    print(f"       Good  {cm[1][0]:4d}   {cm[1][1]:4d}")
    
    print("\n" + "=" * 80)
    print("STEP 9: SAVING MODEL AND SCALER")
    print("=" * 80)
    
    with open(MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    print(f"✓ Model saved to {MODEL_PATH}")
    
    with open(SCALER_PATH, 'wb') as f:
        pickle.dump(scaler, f)
    print(f"✓ Scaler saved to {SCALER_PATH}")
    
    print("\n" + "=" * 80)
    print("TRAINING COMPLETE!")
    print("=" * 80)
    
    return {
        'accuracy': accuracy,
        'precision': precision,
        'recall': recall,
        'f1_score': f1,
        'confusion_matrix': cm.tolist(),
        'num_samples': len(X),
        'train_size': len(X_train),
        'test_size': len(X_test),
    }


def predict_issue_quality(issue: Dict, profile_data: Optional[Dict] = None) -> Tuple[float, float]:
    """
    Predict whether an issue is "good" or "bad" using the trained ML model.
    
    Args:
        issue: Issue dictionary from database
        profile_data: Optional profile data for calculating match scores
        
    Returns:
        Tuple of (probability_good, probability_bad)
    """
    if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
        return 0.5, 0.5  # Neutral prediction
    
    try:
        with open(MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
        with open(SCALER_PATH, 'rb') as f:
            scaler = pickle.load(f)
        
        features = extract_features(issue, profile_data)
        X = np.array([features])
        X_scaled = scaler.transform(X)
        
        proba = model.predict_proba(X_scaled)[0]
        return proba[1], proba[0]  # (good_prob, bad_prob)
    
    except Exception as e:
        print(f"Warning: Error in ML prediction: {e}")
        return 0.5, 0.5  # Neutral prediction

