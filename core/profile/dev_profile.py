import contextlib
import json
import os
from datetime import datetime

import requests  # type: ignore[import-untyped]
from dotenv import load_dotenv

from core.constants import GITHUB_API_BASE
from core.parsing.skill_extractor import analyze_job_text

with contextlib.suppress(PermissionError):
    load_dotenv()
GITHUB_TOKEN = os.getenv("PAT_TOKEN")

DEV_PROFILE_JSON = "dev_profile.json"


def create_profile_from_github(username: str) -> dict:
    """
    Create developer profile from GitHub username.

    Args:
        username: GitHub username

    Returns:
        Dictionary with profile data
    """

    print(f"Fetching GitHub profile for: {username}")

    # Get user info
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "ContributionMatcher/1.0"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    user_url = f"{GITHUB_API_BASE}/users/{username}"
    user_response = requests.get(user_url, headers=headers, timeout=30)
    if user_response.status_code != 200:
        raise ValueError(f"Could not fetch GitHub user: {username}")

    user_data = user_response.json()

    # Get user's repositories
    repos_url = f"{GITHUB_API_BASE}/users/{username}/repos"
    repos_response = requests.get(
        repos_url,
        headers=headers,
        params={"per_page": 100, "sort": "updated"},  # type: ignore[arg-type]
        timeout=30,
    )
    repos = repos_response.json() if repos_response.status_code == 200 else []

    # Extract languages from all repos
    all_languages: dict[str, int] = {}
    interests = set()

    for repo in repos[:50]:  # Limit to 50 most recent repos
        repo.get("name", "")
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
            account_created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
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


def create_profile_from_resume(pdf_path: str) -> dict:
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
            raise ImportError(
                "No PDF library available. Install PyPDF2 or pdfplumber: pip install PyPDF2"
            )

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"Resume PDF not found: {pdf_path}")

    text_parts = []
    if PDF_LIBRARY == "PyPDF2":
        with open(pdf_path, "rb") as f:
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
        r"(\d+)\+?\s*years?\s*(?:of\s+)?(?:experience|exp)",
        r"(\d+)\+?\s*yrs?\s*(?:of\s+)?(?:experience|exp)",
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


def create_profile_manual(profile_data: dict) -> dict:
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


def save_dev_profile(
    profile: dict, output_path: str = DEV_PROFILE_JSON, encrypt: bool = True
) -> None:
    """
    Save developer profile to JSON file and database.

    Args:
        profile: Dictionary with profile data
        output_path: Path to output JSON file
        encrypt: Whether to encrypt the profile file
    """

    # Save to JSON file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    # Encrypt if requested
    if encrypt:
        try:
            # Encryption functionality not yet implemented
            # from core.security.encryption import encrypt_profile
            # encrypt_profile(output_path)
            pass  # type: ignore[unreachable]
            os.remove(output_path)  # Remove unencrypted file
            print(f"Profile encrypted and saved to {output_path}.encrypted")
        except ImportError:
            print("Warning: cryptography not installed, profile saved unencrypted")
        except Exception as e:
            print(f"Warning: Encryption failed: {e}. Profile saved unencrypted.")

    print(f"Profile saved to {output_path}")

    # Save to database using ORM
    try:
        from core.config import get_settings
        from core.db import db
        from core.models import DevProfile as DevProfileModel

        settings = get_settings()
        if not db.is_initialized:
            db.initialize(settings.database_url)

        with db.session() as session:
            # Check if profile exists (for user_id=1, CLI default)
            existing = session.query(DevProfileModel).filter(DevProfileModel.user_id == 1).first()

            if existing:
                # Update existing profile
                existing.skills = profile.get("skills", [])
                existing.experience_level = profile.get("experience_level", "beginner")
                existing.interests = profile.get("interests", [])
                existing.preferred_languages = profile.get("preferred_languages", [])
                existing.time_availability_hours_per_week = profile.get(
                    "time_availability_hours_per_week"
                )
            else:
                # Insert new profile
                new_profile = DevProfileModel(
                    user_id=1,  # CLI default user
                    skills=profile.get("skills", []),
                    experience_level=profile.get("experience_level", "beginner"),
                    interests=profile.get("interests", []),
                    preferred_languages=profile.get("preferred_languages", []),
                    time_availability_hours_per_week=profile.get(
                        "time_availability_hours_per_week"
                    ),
                )
                session.add(new_profile)
    except Exception as e:
        print(f"Warning: Could not save profile to database: {e}")


def load_dev_profile(json_path: str = DEV_PROFILE_JSON, encrypted: bool | None = None) -> dict:
    """
    Load developer profile from JSON file.

    Args:
        json_path: Path to JSON file
        encrypted: Whether the file is encrypted

    Returns:
        Dictionary with profile data
    """

    # Check for encrypted file first (default behavior)
    encrypted_path = json_path + ".encrypted"
    if encrypted is None:
        # Auto-detect: prefer encrypted if it exists
        if os.path.exists(encrypted_path):
            encrypted = True
        else:
            encrypted = False

    if encrypted or json_path.endswith(".encrypted"):
        try:
            from core.security.encryption import get_encryption_service

            service = get_encryption_service()
            if not service.is_available:
                # Fall back to unencrypted file if encryption is unavailable
                if os.path.exists(json_path) and not json_path.endswith(".encrypted"):
                    with open(json_path, encoding="utf-8") as f:
                        return json.load(f)
                raise ImportError(
                    "Encryption service not available and no unencrypted profile found"
                )

            # Read encrypted file and decrypt
            file_to_read = encrypted_path if os.path.exists(encrypted_path) else json_path
            with open(file_to_read, encoding="utf-8") as f:
                encrypted_data = f.read()
            decrypted_data = service.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except ImportError as e:
            # Fall back to unencrypted file if exists
            if os.path.exists(json_path) and not json_path.endswith(".encrypted"):
                with open(json_path, encoding="utf-8") as f:
                    return json.load(f)
            raise ImportError(
                "cryptography is required for encrypted profiles. Install with: pip install cryptography"
            ) from e
        except Exception as e:
            # Fall back to unencrypted file if exists
            if os.path.exists(json_path) and not json_path.endswith(".encrypted"):
                with open(json_path, encoding="utf-8") as f:
                    return json.load(f)
            raise ValueError(f"Failed to decrypt profile: {e}")

    # Load unencrypted file
    if not os.path.exists(json_path):
        raise FileNotFoundError(
            f"Developer profile not found: {json_path}. "
            f"Run 'python contribution_matcher.py create-profile' first."
        )

    with open(json_path, encoding="utf-8") as f:
        return json.load(f)
