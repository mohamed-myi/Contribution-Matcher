import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from contribution_matcher.config import GITHUB_API_BASE
import requests
from dotenv import load_dotenv

load_dotenv()
GITHUB_TOKEN = os.getenv("PAT_TOKEN")
from contribution_matcher.parsing.skill_extractor import analyze_job_text

DEV_PROFILE_JSON = "dev_profile.json"


def create_profile_from_github(username: str) -> Dict:
    """
    Create developer profile from GitHub username.
    
    Args:
        username: GitHub username
        
    Returns:
        Dictionary with profile data
    """
    print(f"Fetching GitHub profile for: {username}")
    
    # Get user info
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ContributionMatcher/1.0"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    
    user_url = f"{GITHUB_API_BASE}/users/{username}"
    user_response = requests.get(user_url, headers=headers, timeout=30)
    if user_response.status_code != 200:
        raise ValueError(f"Could not fetch GitHub user: {username}")
    
    user_data = user_response.json()
    
    # Get user's repositories
    repos_url = f"{GITHUB_API_BASE}/users/{username}/repos"
    repos_response = requests.get(repos_url, headers=headers, params={"per_page": 100, "sort": "updated"}, timeout=30)
    repos = repos_response.json() if repos_response.status_code == 200 else []
    
    # Extract languages from all repos
    all_languages = {}
    interests = set()
    
    for repo in repos[:50]:  # Limit to 50 most recent repos
        repo_name = repo.get("name", "")
        repo_languages_url = repo.get("languages_url", "")
        
        if repo_languages_url:
            lang_response = requests.get(repo_languages_url, headers=headers, timeout=30)
            if lang_response.status_code == 200:
                repo_languages = lang_response.json()
                for lang, bytes_count in repo_languages.items():
                    all_languages[lang] = all_languages.get(lang, 0) + bytes_count
        
        # Extract topics as interests
        topics = repo.get("topics", [])
        interests.update(topics)
    
    # Get skills from languages
    skills = list(all_languages.keys())
    
    # Infer experience level from account age and activity
    created_at = user_data.get("created_at", "")
    experience_level = "beginner"
    if created_at:
        try:
            account_created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            years_active = (datetime.now(account_created.tzinfo) - account_created).days / 365.25
            
            if years_active >= 5:
                experience_level = "advanced"
            elif years_active >= 2:
                experience_level = "intermediate"
        except (ValueError, AttributeError):
            pass
    
    # Get preferred languages (top languages by usage)
    preferred_languages = sorted(all_languages.items(), key=lambda x: x[1], reverse=True)[:5]
    preferred_languages = [lang for lang, _ in preferred_languages]
    
    profile = {
        "skills": skills,
        "experience_level": experience_level,
        "interests": list(interests),
        "preferred_languages": preferred_languages,
        "time_availability_hours_per_week": None,  # User should set this manually
    }
    
    save_dev_profile(profile)
    print(f"Profile created with {len(skills)} skills and {len(interests)} interests")
    
    return profile


def create_profile_from_resume(pdf_path: str) -> Dict:
    """
    Create developer profile from resume PDF.
    
    Args:
        pdf_path: Path to resume PDF file
        
    Returns:
        Dictionary with profile data
    """
    # Use basic PDF parsing
    try:
        import PyPDF2
        PDF_LIBRARY = "PyPDF2"
    except ImportError:
        try:
            import pdfplumber
            PDF_LIBRARY = "pdfplumber"
        except ImportError:
            raise ImportError("No PDF library available. Install PyPDF2 or pdfplumber: pip install PyPDF2")
    
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")
    
    text_parts = []
    if PDF_LIBRARY == "PyPDF2":
        with open(pdf_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
    elif PDF_LIBRARY == "pdfplumber":
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)
    
    resume_text = "\n".join(text_parts)
    
    # Extract skills using skill extractor
    category, skills, _ = analyze_job_text(resume_text)
    
    # Try to extract experience years from text
    import re
    experience_years = None
    exp_patterns = [
        r'(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)',
        r'(\d+)\+?\s*yrs?\s*(?:of\s+)?(?:experience|exp)',
    ]
    for pattern in exp_patterns:
        match = re.search(pattern, resume_text.lower())
        if match:
            try:
                experience_years = int(match.group(1))
                break
            except (ValueError, IndexError):
                continue
    
    # Infer experience level
    experience_level = "beginner"
    if experience_years:
        if experience_years >= 5:
            experience_level = "advanced"
        elif experience_years >= 2:
            experience_level = "intermediate"
    
    profile = {
        "skills": [skill for skill, _ in skills],
        "experience_level": experience_level,
        "interests": [],
        "preferred_languages": [skill for skill, _ in skills[:5]],  # Top 5 skills
        "time_availability_hours_per_week": None,
    }
    
    save_dev_profile(profile)
    return profile


def create_profile_manual(profile_data: Dict) -> Dict:
    """
    Create profile from manual input.
    
    Args:
        profile_data: Dictionary with profile fields
        
    Returns:
        Dictionary with profile data
    """
    profile = {
        "skills": profile_data.get("skills", []),
        "experience_level": profile_data.get("experience_level", "intermediate"),
        "interests": profile_data.get("interests", []),
        "preferred_languages": profile_data.get("preferred_languages", []),
        "time_availability_hours_per_week": profile_data.get("time_availability_hours_per_week"),
    }
    
    # Validate
    if profile["experience_level"] not in ["beginner", "intermediate", "advanced"]:
        raise ValueError("experience_level must be 'beginner', 'intermediate', or 'advanced'")
    
    save_dev_profile(profile)
    return profile


def save_dev_profile(profile: Dict, output_path: str = DEV_PROFILE_JSON) -> None:
    """
    Save developer profile to JSON file and database.
    
    Args:
        profile: Dictionary with profile data
        output_path: Path to output JSON file
    """
    # Save to JSON file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)
    
    print(f"Profile saved to {output_path}")
    
    # Save to database
    try:
        from contribution_matcher.database import db_conn
        import json as json_module
        
        with db_conn() as conn:
            cur = conn.cursor()
            
            # Check if profile exists
            cur.execute("SELECT id FROM dev_profile LIMIT 1")
            existing = cur.fetchone()
            
            skills_json = json_module.dumps(profile.get("skills", []))
            interests_json = json_module.dumps(profile.get("interests", []))
            preferred_languages_json = json_module.dumps(profile.get("preferred_languages", []))
            
            if existing:
                # Update existing profile
                cur.execute(
                    """
                    UPDATE dev_profile
                    SET skills = ?, experience_level = ?, interests = ?,
                        preferred_languages = ?, time_availability_hours_per_week = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        skills_json,
                        profile.get("experience_level"),
                        interests_json,
                        preferred_languages_json,
                        profile.get("time_availability_hours_per_week"),
                        existing[0]
                    )
                )
            else:
                # Insert new profile
                cur.execute(
                    """
                    INSERT INTO dev_profile (skills, experience_level, interests, preferred_languages, time_availability_hours_per_week)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        skills_json,
                        profile.get("experience_level"),
                        interests_json,
                        preferred_languages_json,
                        profile.get("time_availability_hours_per_week")
                    )
                )
    except Exception as e:
        print(f"Warning: Could not save profile to database: {e}")


def load_dev_profile(json_path: str = DEV_PROFILE_JSON) -> Dict:
    """
    Load developer profile from JSON file.
    
    Args:
        json_path: Path to JSON file
        
    Returns:
        Dictionary with profile data
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"Developer profile not found: {json_path}. "
            f"Run 'python contribution_matcher.py create-profile' first."
        )
    
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

