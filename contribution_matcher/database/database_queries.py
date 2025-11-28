import csv
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .database import db_conn


def query_issues(
    difficulty: Optional[str] = None,
    technology: Optional[str] = None,
    repo_owner: Optional[str] = None,
    issue_type: Optional[str] = None,
    days_back: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Dict]:
    """
    Query issues from the database with various filters.
    
    Args:
        difficulty: Filter by difficulty ('beginner', 'intermediate', 'advanced')
        technology: Filter by technology name (case-insensitive partial match)
        repo_owner: Filter by repository owner
        issue_type: Filter by issue type ('bug', 'feature', 'documentation', etc.)
        days_back: Only return issues created in the last N days
        limit: Maximum number of results to return
    
    Returns:
        List of issue dictionaries with all fields
    """
    with db_conn() as conn:
        cur = conn.cursor()
        
        query = "SELECT * FROM issues WHERE 1=1"
        params = []
        
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        
        if repo_owner:
            query += " AND repo_owner LIKE ?"
            params.append(f"%{repo_owner}%")
        
        if issue_type:
            query += " AND issue_type = ?"
            params.append(issue_type)
        
        if days_back:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            query += " AND created_at >= ?"
            params.append(cutoff_date)
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Get column names
        columns = [description[0] for description in cur.description]
        
        # Convert to list of dictionaries
        issues = []
        for row in rows:
            issue = dict(zip(columns, row))
            
            # Parse JSON fields
            if issue.get("labels"):
                try:
                    issue["labels"] = json.loads(issue["labels"])
                except (json.JSONDecodeError, TypeError):
                    issue["labels"] = []
            
            if issue.get("repo_languages"):
                try:
                    issue["repo_languages"] = json.loads(issue["repo_languages"])
                except (json.JSONDecodeError, TypeError):
                    issue["repo_languages"] = {}
            
            if issue.get("repo_topics"):
                try:
                    issue["repo_topics"] = json.loads(issue["repo_topics"])
                except (json.JSONDecodeError, TypeError):
                    issue["repo_topics"] = []
            
            # If technology filter is specified, check if issue has that technology
            if technology:
                cur.execute(
                    """
                    SELECT COUNT(*) FROM issue_technologies
                    WHERE issue_id = ? AND LOWER(technology) LIKE ?
                    """,
                    (issue['id'], f"%{technology.lower()}%")
                )
                if cur.fetchone()[0] == 0:
                    continue
            
            issues.append(issue)
        
        return issues


def get_issue_technologies(issue_id: int) -> List[Tuple[str, Optional[str]]]:
    """
    Get all technologies for a specific issue.
    
    Returns:
        List of (technology, technology_category) tuples
    """
    with db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT technology, technology_category FROM issue_technologies WHERE issue_id = ? ORDER BY technology",
            (issue_id,)
        )
        return cur.fetchall()


def get_statistics() -> Dict:
    """
    Get aggregate statistics about stored issues.
    
    Returns:
        Dictionary with various statistics
    """
    with db_conn() as conn:
        cur = conn.cursor()
        
        stats = {}
        
        # Total issues
        cur.execute("SELECT COUNT(*) FROM issues")
        stats['total_issues'] = cur.fetchone()[0]
        
        # Issues by difficulty
        cur.execute(
            """
            SELECT difficulty, COUNT(*) as count
            FROM issues
            WHERE difficulty IS NOT NULL
            GROUP BY difficulty
            ORDER BY count DESC
            """
        )
        stats['issues_by_difficulty'] = dict(cur.fetchall())
        
        # Issues by type
        cur.execute(
            """
            SELECT issue_type, COUNT(*) as count
            FROM issues
            WHERE issue_type IS NOT NULL
            GROUP BY issue_type
            ORDER BY count DESC
            """
        )
        stats['issues_by_type'] = dict(cur.fetchall())
        
        # Most common technologies
        cur.execute(
            """
            SELECT technology, COUNT(*) as count
            FROM issue_technologies
            GROUP BY technology
            ORDER BY count DESC
            LIMIT 20
            """
        )
        stats['top_technologies'] = dict(cur.fetchall())
        
        # Most common repos
        cur.execute(
            """
            SELECT repo_name, COUNT(*) as count
            FROM issues
            WHERE repo_name IS NOT NULL
            GROUP BY repo_name
            ORDER BY count DESC
            LIMIT 20
            """
        )
        stats['top_repos'] = dict(cur.fetchall())
        
        # Recent issues (last 7 days)
        cutoff_date = (datetime.now() - timedelta(days=7)).isoformat()
        cur.execute("SELECT COUNT(*) FROM issues WHERE created_at >= ?", (cutoff_date,))
        stats['issues_last_7_days'] = cur.fetchone()[0]
        
        # Average technologies per issue
        cur.execute(
            """
            SELECT AVG(tech_count) FROM (
                SELECT COUNT(*) as tech_count
                FROM issue_technologies
                GROUP BY issue_id
            )
            """
        )
        result = cur.fetchone()[0]
        stats['avg_technologies_per_issue'] = round(result, 2) if result else 0
        
        return stats


def export_to_csv(output_file: str, issues: Optional[List[Dict]] = None) -> None:
    """
    Export issues to CSV file.
    
    Args:
        output_file: Path to output CSV file
        issues: Optional list of issues to export. If None, exports all issues.
    """
    if issues is None:
        issues = query_issues()
    
    if not issues:
        print("No issues to export")
        return
    
    # Flatten JSON fields for CSV
    csv_issues = []
    for issue in issues:
        csv_issue = issue.copy()
        # Convert JSON fields to strings
        if csv_issue.get("labels"):
            csv_issue["labels"] = ", ".join(csv_issue["labels"]) if isinstance(csv_issue["labels"], list) else str(csv_issue["labels"])
        if csv_issue.get("repo_topics"):
            csv_issue["repo_topics"] = ", ".join(csv_issue["repo_topics"]) if isinstance(csv_issue["repo_topics"], list) else str(csv_issue["repo_topics"])
        csv_issues.append(csv_issue)
    
    # Get all unique keys from all issues
    fieldnames = set()
    for issue in csv_issues:
        fieldnames.update(issue.keys())
    fieldnames = sorted(fieldnames)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_issues)
    
    print(f"Exported {len(csv_issues)} issues to {output_file}")


def export_to_json(output_file: str, issues: Optional[List[Dict]] = None) -> None:
    """
    Export issues to JSON file.
    
    Args:
        output_file: Path to output JSON file
        issues: Optional list of issues to export. If None, exports all issues.
    """
    if issues is None:
        issues = query_issues()
    
    if not issues:
        print("No issues to export")
        return
    
    # Add technologies to each issue
    for issue in issues:
        issue['technologies'] = [tech for tech, _ in get_issue_technologies(issue['id'])]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(issues, f, indent=2, ensure_ascii=False)
    
    print(f"Exported {len(issues)} issues to {output_file}")


def query_unlabeled_issues(
    difficulty: Optional[str] = None,
    limit: Optional[int] = None,
) -> List[Dict]:
    """
    Query unlabeled issues for labeling export.
    
    Args:
        difficulty: Filter by difficulty
        limit: Maximum number of results
    
    Returns:
        List of unlabeled issue dictionaries
    """
    with db_conn() as conn:
        cur = conn.cursor()
        
        query = "SELECT * FROM issues WHERE (label IS NULL OR label = '')"
        params = []
        
        if difficulty:
            query += " AND difficulty = ?"
            params.append(difficulty)
        
        query += " ORDER BY created_at DESC"
        
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        
        cur.execute(query, params)
        rows = cur.fetchall()
        
        # Get column names
        columns = [description[0] for description in cur.description]
        
        issues = []
        for row in rows:
            issue = dict(zip(columns, row))
            
            # Parse JSON fields
            if issue.get("labels"):
                try:
                    issue["labels"] = json.loads(issue["labels"])
                except (json.JSONDecodeError, TypeError):
                    issue["labels"] = []
            
            issues.append(issue)
        
        return issues


def get_labeling_statistics() -> Dict:
    """
    Get statistics about labeled issues.
    
    Returns:
        Dictionary with labeling statistics
    """
    with db_conn() as conn:
        cur = conn.cursor()
        
        stats = {}
        
        # Total issues
        cur.execute("SELECT COUNT(*) FROM issues")
        stats['total_issues'] = cur.fetchone()[0]
        
        # Labeled issues
        cur.execute("SELECT COUNT(*) FROM issues WHERE label IS NOT NULL AND label != ''")
        stats['labeled_issues'] = cur.fetchone()[0]
        
        # Unlabeled issues
        stats['unlabeled_issues'] = stats['total_issues'] - stats['labeled_issues']
        
        # Good issues
        cur.execute("SELECT COUNT(*) FROM issues WHERE label = 'good'")
        stats['good_issues'] = cur.fetchone()[0]
        
        # Bad issues
        cur.execute("SELECT COUNT(*) FROM issues WHERE label = 'bad'")
        stats['bad_issues'] = cur.fetchone()[0]
        
        # Progress toward 200 minimum
        stats['progress_to_200'] = min(100, (stats['labeled_issues'] / 200) * 100) if stats['labeled_issues'] < 200 else 100
        stats['remaining_to_200'] = max(0, 200 - stats['labeled_issues'])
        
        # Balanced labeling check
        stats['is_balanced'] = abs(stats['good_issues'] - stats['bad_issues']) <= 10
        
        return stats

