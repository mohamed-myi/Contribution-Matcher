"""DEPRECATED: Legacy SQLite database module. Use core.database and core.repositories instead."""

import json
import os
import pickle
import sqlite3
import warnings
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


warnings.warn(
    "core.database.database is deprecated. Use core.database and core.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)


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
    # Create tables if they do not already exist

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
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issue_technologies_technology ON issue_technologies(technology);")
        
        # Add indexes for variety queries
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_difficulty ON issues(difficulty);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_issue_type ON issues(issue_type);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_is_active ON issues(is_active);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_created_at ON issues(created_at);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issues_repo_owner ON issues(repo_owner);")

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

        # Issue embeddings table (for caching BERT embeddings)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS issue_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_id INTEGER NOT NULL,
                description_embedding BLOB,
                title_embedding BLOB,
                embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(issue_id),
                FOREIGN KEY (issue_id) REFERENCES issues(id) ON DELETE CASCADE
            );
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_issue_embeddings_issue_id ON issue_embeddings(issue_id);")


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
    is_active: int = 1,
) -> int:
    """DEPRECATED: Use IssueRepository.bulk_upsert() instead."""
    warnings.warn(
        "upsert_issue is deprecated. Use IssueRepository.bulk_upsert() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    """Replace issue_technologies entries for a given issue."""
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
    """Update the label for an issue ('good' or 'bad'). Returns True if successful."""
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
    DEPRECATED: Use RepoMetadataRepository.upsert() instead.

    Insert or update repo metadata for caching.
    """
    warnings.warn(
        "upsert_repo_metadata is deprecated. Use RepoMetadataRepository.upsert() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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
    DEPRECATED: Use RepoMetadataRepository.get() instead.

    Get cached repo metadata from database.
    
    Returns:
        Dictionary with repo metadata or None if not found
    """
    warnings.warn(
        "get_repo_metadata is deprecated. Use RepoMetadataRepository.get() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
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


def upsert_issue_embedding(
    issue_id: int,
    description_embedding: np.ndarray,
    title_embedding: np.ndarray,
    embedding_model: str = 'all-MiniLM-L6-v2',
) -> None:
    '''
    Store or update BERT embeddings for an issue.
    
    Args:
        issue_id: The issue ID
        description_embedding: NumPy array of description embedding (384-dim)
        title_embedding: NumPy array of title embedding (384-dim)
        embedding_model: Model name used for embeddings
    '''
    with db_conn() as conn:
        cur = conn.cursor()
        
        # Serialize embeddings to BLOB
        desc_blob = pickle.dumps(description_embedding)
        title_blob = pickle.dumps(title_embedding)
        
        cur.execute(
            """
            INSERT INTO issue_embeddings (
                issue_id, description_embedding, title_embedding, embedding_model
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(issue_id) DO UPDATE SET
                description_embedding=excluded.description_embedding,
                title_embedding=excluded.title_embedding,
                embedding_model=excluded.embedding_model,
                created_at=CURRENT_TIMESTAMP;
            """,
            (issue_id, desc_blob, title_blob, embedding_model),
        )


def get_issue_embedding(issue_id: int) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    '''
    Retrieve cached BERT embeddings for an issue.
    
    Args:
        issue_id: The issue ID
        
    Returns:
        Tuple of (description_embedding, title_embedding) or None if not found
    '''
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT description_embedding, title_embedding FROM issue_embeddings WHERE issue_id = ?;",
            (issue_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        
        desc_blob, title_blob = row
        description_embedding = pickle.loads(desc_blob)
        title_embedding = pickle.loads(title_blob)
        
        return description_embedding, title_embedding


# =============================================================================
# Query Functions (formerly in database_queries.py)
# =============================================================================

def query_issues(
    difficulty: Optional[str] = None,
    issue_type: Optional[str] = None,
    label: Optional[str] = None,
    is_active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict]:
    """
    Query issues with optional filters.
    """
    # Ensure limit and offset are integers
    if limit is None:
        limit = 100
    if offset is None:
        offset = 0
    limit = int(limit)
    offset = int(offset)
    
    with db_conn() as conn:
        cur = conn.cursor()
        
        query = "SELECT * FROM issues WHERE 1=1"
        params = []
        
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        if issue_type:
            query += " AND issue_type = ?"
            params.append(issue_type)
        if label:
            query += " AND label = ?"
            params.append(label)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        columns = [description[0] for description in cur.description]
        
        results = []
        for row in cur.fetchall():
            issue = dict(zip(columns, row))
            # Parse JSON fields
            if issue.get('labels'):
                issue['labels'] = json.loads(issue['labels'])
            if issue.get('repo_languages'):
                issue['repo_languages'] = json.loads(issue['repo_languages'])
            if issue.get('repo_topics'):
                issue['repo_topics'] = json.loads(issue['repo_topics'])
            results.append(issue)
        
        return results


def query_unlabeled_issues(limit: int = 100) -> List[Dict]:
    """Query issues without labels for ML training data collection."""
    # Ensure limit is an integer
    if limit is None:
        limit = 100
    limit = int(limit)
    
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM issues WHERE label IS NULL AND is_active = 1 ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        columns = [description[0] for description in cur.description]
        
        results = []
        for row in cur.fetchall():
            issue = dict(zip(columns, row))
            if issue.get('labels'):
                issue['labels'] = json.loads(issue['labels'])
            if issue.get('repo_languages'):
                issue['repo_languages'] = json.loads(issue['repo_languages'])
            if issue.get('repo_topics'):
                issue['repo_topics'] = json.loads(issue['repo_topics'])
            results.append(issue)
        
        return results


def get_issue_technologies(issue_id: int) -> List[Tuple[str, Optional[str]]]:
    """Get technologies for an issue."""
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT technology, technology_category FROM issue_technologies WHERE issue_id = ?",
            (issue_id,)
        )
        return cur.fetchall()


def get_all_issue_urls() -> List[str]:
    """Get all issue URLs in the database."""
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT url FROM issues")
        return [row[0] for row in cur.fetchall()]


def mark_issues_inactive(urls: List[str]) -> int:
    """Mark issues as inactive by their URLs."""
    if not urls:
        return 0
    
    with db_conn() as conn:
        cur = conn.cursor()
        placeholders = ",".join("?" for _ in urls)
        cur.execute(
            f"UPDATE issues SET is_active = 0 WHERE url IN ({placeholders})",
            urls
        )
        return cur.rowcount


def get_statistics() -> Dict:
    """Get database statistics."""
    with db_conn() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT COUNT(*) FROM issues")
        total_issues = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM issues WHERE is_active = 1")
        active_issues = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM issues WHERE label IS NOT NULL")
        labeled_issues = cur.fetchone()[0]
        
        cur.execute("SELECT difficulty, COUNT(*) FROM issues GROUP BY difficulty")
        by_difficulty = dict(cur.fetchall())
        
        return {
            "total_issues": total_issues,
            "active_issues": active_issues,
            "labeled_issues": labeled_issues,
            "by_difficulty": by_difficulty,
        }


def get_variety_statistics() -> Dict:
    """Get variety statistics for issues."""
    with db_conn() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT difficulty, COUNT(*) FROM issues WHERE is_active = 1 GROUP BY difficulty")
        by_difficulty = dict(cur.fetchall())
        
        cur.execute("SELECT issue_type, COUNT(*) FROM issues WHERE is_active = 1 GROUP BY issue_type")
        by_type = dict(cur.fetchall())
        
        cur.execute("SELECT repo_owner, COUNT(*) FROM issues WHERE is_active = 1 GROUP BY repo_owner ORDER BY COUNT(*) DESC LIMIT 10")
        top_repos = dict(cur.fetchall())
        
        return {
            "by_difficulty": by_difficulty,
            "by_type": by_type,
            "top_repos": top_repos,
        }


def get_labeling_statistics() -> Dict:
    """Get labeling statistics for ML training."""
    with db_conn() as conn:
        cur = conn.cursor()
        
        cur.execute("SELECT label, COUNT(*) FROM issues WHERE label IS NOT NULL GROUP BY label")
        by_label = dict(cur.fetchall())
        
        return {
            "total_labeled": sum(by_label.values()) if by_label else 0,
            "by_label": by_label,
        }


def export_to_csv(filepath: str, filter_bookmarked: bool = False) -> int:
    """Export issues to CSV file."""
    import csv
    
    issues = query_issues(is_active=True, limit=10000)
    
    if not issues:
        return 0
    
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=issues[0].keys())
        writer.writeheader()
        writer.writerows(issues)
    
    return len(issues)


def export_to_json(filepath: str, filter_bookmarked: bool = False) -> int:
    """Export issues to JSON file."""
    issues = query_issues(is_active=True, limit=10000)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(issues, f, indent=2, default=str)
    
    return len(issues)

