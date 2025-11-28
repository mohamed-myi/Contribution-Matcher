import json
import os
import sqlite3
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional, Tuple


DB_PATH = os.getenv("CONTRIBUTION_MATCHER_DB_PATH", "contribution_matcher.db")


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def db_conn():
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not already exist."""
    with db_conn() as conn:
        cur = conn.cursor()

        # Issues table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                body TEXT,
                repo_owner TEXT,
                repo_name TEXT,
                repo_url TEXT,
                difficulty TEXT,
                issue_type TEXT,
                time_estimate TEXT,
                labels TEXT,
                repo_stars INTEGER,
                repo_forks INTEGER,
                repo_languages TEXT,
                repo_topics TEXT,
                last_commit_date TEXT,
                contributor_count INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                label TEXT,
                labeled_at TEXT
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_url ON issues(url);")

        # Issue technologies table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_technologies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id INTEGER NOT NULL,
                technology TEXT NOT NULL,
                technology_category TEXT,
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issue_technologies_issue_id ON issue_technologies(issue_id);")

        # Repo metadata table (for caching)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS repo_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repo_owner TEXT NOT NULL,
                repo_name TEXT NOT NULL,
                stars INTEGER,
                forks INTEGER,
                languages TEXT,
                topics TEXT,
                last_commit_date TEXT,
                contributor_count INTEGER,
                cached_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(repo_owner, repo_name)
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_repo_metadata_lookup ON repo_metadata(repo_owner, repo_name);")

        # Dev profile table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS dev_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skills TEXT,
                experience_level TEXT,
                interests TEXT,
                preferred_languages TEXT,
                time_availability_hours_per_week INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


def upsert_issue(
    title: str,
    url: str,
    body: Optional[str] = None,
    repo_owner: Optional[str] = None,
    repo_name: Optional[str] = None,
    repo_url: Optional[str] = None,
    difficulty: Optional[str] = None,
    issue_type: Optional[str] = None,
    time_estimate: Optional[str] = None,
    labels: Optional[List[str]] = None,
    repo_stars: Optional[int] = None,
    repo_forks: Optional[int] = None,
    repo_languages: Optional[Dict[str, int]] = None,
    repo_topics: Optional[List[str]] = None,
    last_commit_date: Optional[str] = None,
    contributor_count: Optional[int] = None,
    is_active: Optional[int] = None,
) -> int:
    """

    Insert or update an issue row and return its id.
    Issues are uniquely identified by URL.

    """
    with db_conn() as conn:
        cur = conn.cursor()

        # Convert lists/dicts to JSON strings
        labels_json = json.dumps(labels) if labels else None
        languages_json = json.dumps(repo_languages) if repo_languages else None
        topics_json = json.dumps(repo_topics) if repo_topics else None

        cur.execute(
            """
            INSERT INTO issues (
                title, url, body, repo_owner, repo_name, repo_url,
                difficulty, issue_type, time_estimate, labels,
                repo_stars, repo_forks, repo_languages, repo_topics,
                last_commit_date, contributor_count, is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title=excluded.title,
                body=excluded.body,
                repo_owner=excluded.repo_owner,
                repo_name=excluded.repo_name,
                repo_url=excluded.repo_url,
                difficulty=excluded.difficulty,
                issue_type=excluded.issue_type,
                time_estimate=excluded.time_estimate,
                labels=excluded.labels,
                repo_stars=excluded.repo_stars,
                repo_forks=excluded.repo_forks,
                repo_languages=excluded.repo_languages,
                repo_topics=excluded.repo_topics,
                last_commit_date=excluded.last_commit_date,
                contributor_count=excluded.contributor_count,
                is_active=excluded.is_active,
                updated_at=CURRENT_TIMESTAMP;
            """,
            (
                title, url, body, repo_owner, repo_name, repo_url,
                difficulty, issue_type, time_estimate, labels_json,
                repo_stars, repo_forks, languages_json, topics_json,
                last_commit_date, contributor_count, is_active
            ),
        )

        # Fetch id
        cur.execute("SELECT id FROM issues WHERE url = ?;", (url,))
        row = cur.fetchone()
        assert row is not None
        return int(row[0])


def replace_issue_technologies(
    issue_id: int,
    technologies: Iterable[Tuple[str, Optional[str]]],
) -> None:
    """
    Replace issue_technologies entries for a given issue.
    """
    with db_conn() as conn:
        cur = conn.cursor()

        cur.execute("DELETE FROM issue_technologies WHERE issue_id = ?;", (issue_id,))

        tech_rows: List[Tuple[int, str, Optional[str]]] = []
        for tech, tech_category in technologies:
            tech_rows.append((issue_id, tech, tech_category))

        if tech_rows:
            cur.executemany(
                "INSERT INTO issue_technologies (issue_id, technology, technology_category) VALUES (?, ?, ?);",
                tech_rows,
            )


def update_issue_label(issue_id: int, label: str) -> bool:
    """
    Update the label for an issue.
    
    Args:
        issue_id: The issue ID
        label: The label ('good' or 'bad')
        
    Returns:
        True if successful, False otherwise
    """
    if label not in ['good', 'bad']:
        return False
    
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE issues 
            SET label = ?, labeled_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (label, issue_id)
        )
        return cur.rowcount > 0


def upsert_repo_metadata(
    repo_owner: str,
    repo_name: str,
    stars: Optional[int] = None,
    forks: Optional[int] = None,
    languages: Optional[Dict[str, int]] = None,
    topics: Optional[List[str]] = None,
    last_commit_date: Optional[str] = None,
    contributor_count: Optional[int] = None,
) -> None:
    """
    Insert or update repo metadata for caching.
    """
    with db_conn() as conn:
        cur = conn.cursor()

        languages_json = json.dumps(languages) if languages else None
        topics_json = json.dumps(topics) if topics else None

        cur.execute(
            """
            INSERT INTO repo_metadata (
                repo_owner, repo_name, stars, forks, languages, topics,
                last_commit_date, contributor_count, cached_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(repo_owner, repo_name) DO UPDATE SET
                stars=excluded.stars,
                forks=excluded.forks,
                languages=excluded.languages,
                topics=excluded.topics,
                last_commit_date=excluded.last_commit_date,
                contributor_count=excluded.contributor_count,
                cached_at=CURRENT_TIMESTAMP;
            """,
            (repo_owner, repo_name, stars, forks, languages_json, topics_json,
             last_commit_date, contributor_count),
        )


def get_repo_metadata(repo_owner: str, repo_name: str) -> Optional[Dict]:
    """
    Get cached repo metadata from database.
    
    Returns:
        Dictionary with repo metadata or None if not found
    """
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM repo_metadata WHERE repo_owner = ? AND repo_name = ?;",
            (repo_owner, repo_name)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        columns = [description[0] for description in cur.description]
        metadata = dict(zip(columns, row))
        
        # Parse JSON fields
        if metadata.get('languages'):
            metadata['languages'] = json.loads(metadata['languages'])
        if metadata.get('topics'):
            metadata['topics'] = json.loads(metadata['topics'])
        
        return metadata

