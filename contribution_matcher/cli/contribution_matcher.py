import argparse
import csv
import json
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

from contribution_matcher.database import (
    init_db,
    replace_issue_technologies,
    upsert_issue,
    update_issue_label,
    query_issues,
    get_statistics,
    export_to_csv,
    export_to_json,
    query_unlabeled_issues,
    get_labeling_statistics,
)
from contribution_matcher.profile import (
    create_profile_from_github,
    create_profile_from_resume,
    create_profile_manual,
    load_dev_profile,
    save_dev_profile,
)
from contribution_matcher.api import get_repo_metadata_from_api, search_issues
from contribution_matcher.parsing import parse_issue
from contribution_matcher.scoring import (
    get_top_matches,
    score_issue_against_profile,
    score_profile_against_all_issues,
    train_model,
)
from contribution_matcher.parsing import analyze_job_text

load_dotenv()


def cmd_discover(args):
    """Search for new GitHub issues and store in database."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return

    print(f"\n{'='*60}")
    print("Searching for GitHub Issues")
    print(f"{'='*60}\n")
    
    # Build search parameters
    labels = None
    if args.labels:
        labels = args.labels.split(",")
    
    # Search for issues
    print(f"Searching GitHub for issues...")
    issues = search_issues(
        labels=labels,
        language=args.language,
        min_stars=args.stars,
        limit=args.limit or 100
    )
    
    print(f"Found {len(issues)} issues")
    
    # Process each issue
    new_count = 0
    for issue in issues:
        try:
            # Extract repo info
            repo_url = issue.get("repository_url", "")
            repo_owner = None
            repo_name = None
            if repo_url:
                parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
                if len(parts) >= 2:
                    repo_owner, repo_name = parts[0], parts[1]
            
            # Get repo metadata
            repo_metadata = None
            if repo_owner and repo_name:
                repo_metadata = get_repo_metadata_from_api(repo_owner, repo_name, use_cache=True)
            
            # Parse issue
            parsed = parse_issue(issue, repo_metadata)
            
            # Extract technologies using skill extractor
            issue_body = parsed.get("body", "") or ""
            category, technologies, keyword_counts = analyze_job_text(issue_body)
            
            # Store issue
            issue_id = upsert_issue(
                title=parsed.get("title", ""),
                url=parsed.get("url", ""),
                body=parsed.get("body"),
                repo_owner=parsed.get("repo_owner"),
                repo_name=parsed.get("repo_name"),
                repo_url=parsed.get("repo_url"),
                difficulty=parsed.get("difficulty"),
                issue_type=parsed.get("issue_type"),
                time_estimate=parsed.get("time_estimate"),
                labels=parsed.get("labels", []),
                repo_stars=parsed.get("repo_stars"),
                repo_forks=parsed.get("repo_forks"),
                repo_languages=parsed.get("repo_languages"),
                repo_topics=parsed.get("repo_topics"),
                last_commit_date=parsed.get("last_commit_date"),
                contributor_count=parsed.get("contributor_count"),
                is_active=parsed.get("is_active"),
            )
            
            # Store technologies
            replace_issue_technologies(issue_id, technologies)
            
            new_count += 1
            
        except Exception as e:
            print(f"Error processing issue {issue.get('html_url', 'unknown')}: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"Search complete: Processed {new_count} issues")
    print(f"{'='*60}\n")


def cmd_list(args):
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    issues = query_issues(
        difficulty=args.difficulty,
        technology=args.technology,
        repo_owner=args.repo_owner,
        issue_type=args.issue_type,
        days_back=args.days_back,
        limit=args.limit,
    )
    
    if not issues:
        print("No issues found matching the criteria.")
        return
    
    print(f"\nFound {len(issues)} issue(s):\n")
    print("=" * 80)
    
    for issue in issues:
        print(f"\nTitle: {issue.get('title', 'N/A')}")
        if issue.get('repo_name'):
            print(f"Repository: {issue.get('repo_owner', '')}/{issue.get('repo_name', '')}")
        if issue.get('difficulty'):
            print(f"Difficulty: {issue['difficulty']}")
        if issue.get('issue_type'):
            print(f"Type: {issue['issue_type']}")
        if issue.get('time_estimate'):
            print(f"Time Estimate: {issue['time_estimate']}")
        if issue.get('repo_stars'):
            print(f"Stars: {issue['repo_stars']}")
        print(f"URL: {issue.get('url', 'N/A')}")
        print(f"Created: {issue.get('created_at', 'N/A')}")
        print("-" * 80)


def cmd_score(args):
    """Score profile against issues."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    # Load profile
    try:
        profile = load_dev_profile()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run 'python contribution_matcher.py create-profile' first.")
        return
    
    # Score against issues
    if args.issue_id:
        # Score against specific issue
        issues = query_issues()
        issue = None
        for i in issues:
            if i.get("id") == args.issue_id:
                issue = i
                break
        
        if not issue:
            print(f"Issue with ID {args.issue_id} not found.")
            return
        
        score_result = score_issue_against_profile(profile, issue)
        _print_score_result(score_result, args.format == 'json')
    else:
        # Score against multiple issues
        if args.top:
            scores = get_top_matches(profile=profile, limit=args.top)
        else:
            scores = score_profile_against_all_issues(
                profile=profile,
                limit=args.limit
            )
        
        if args.format == 'json':
            print(json.dumps(scores, indent=2))
        else:
            _print_score_results(scores, args.verbose)


def _print_score_result(score_result: Dict, json_format: bool = False):
    if json_format:
        print(json.dumps(score_result, indent=2))
        return
    
    print("\n" + "=" * 80)
    print(f"Issue: {score_result['issue_title']}")
    if score_result.get('repo_name'):
        print(f"Repository: {score_result['repo_name']}")
    print(f"URL: {score_result['url']}")
    print(f"\nMatch Score: {score_result['score']}/100")
    print("-" * 80)
    
    breakdown = score_result['breakdown']
    
    # Skills
    skills = breakdown['skills']
    print(f"\nSkills Match: {skills['match_percentage']:.1f}%")
    print(f"  Matching: {', '.join(skills['matching'][:10])}")
    if skills['missing']:
        print(f"  Missing: {', '.join(skills['missing'][:10])}")
    
    # Experience
    exp = breakdown['experience']
    print(f"\nExperience Score: {exp['score']:.1f}/20")
    print(f"  Profile: {exp.get('profile_level', 'N/A')}")
    print(f"  Issue difficulty: {exp.get('issue_difficulty', 'N/A')}")
    
    # Repo quality
    repo_quality = breakdown['repo_quality']
    print(f"\nRepo Quality Score: {repo_quality['score']:.1f}/15")
    print(f"  Stars: {repo_quality.get('stars', 'N/A')}")
    print(f"  Forks: {repo_quality.get('forks', 'N/A')}")
    
    print("=" * 80)


def _print_score_results(scores: List[Dict], verbose: bool = False):
    if not scores:
        print("No issues found to score against.")
        return
    
    print(f"\n{'=' * 80}")
    print(f"ISSUE SCORING RESULTS - Top {len(scores)} Matches")
    print(f"{'=' * 80}\n")
    
    for i, score_result in enumerate(scores, 1):
        print(f"{i}. {score_result['issue_title']}")
        if score_result.get('repo_name'):
            print(f"   Repository: {score_result['repo_name']}")
        print(f"   Score: {score_result['score']}/100")
        print(f"   URL: {score_result['url']}")
        
        if verbose:
            breakdown = score_result['breakdown']
            skills = breakdown['skills']
            print(f"   Skills: {skills['match_percentage']:.1f}% match")
            if skills['missing']:
                print(f"   Missing: {', '.join(skills['missing'][:5])}")
        
        print()


def cmd_create_profile(args):
    """Create developer profile."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    if args.github:
        try:
            create_profile_from_github(args.github)
        except Exception as e:
            print(f"Error creating profile from GitHub: {e}")
    elif args.resume:
        try:
            create_profile_from_resume(args.resume)
        except Exception as e:
            print(f"Error creating profile from resume: {e}")
    elif args.manual:
        # Interactive profile creation
        print("Creating profile manually...")
        skills_input = input("Enter skills (comma-separated): ")
        skills = [s.strip() for s in skills_input.split(",")] if skills_input else []
        
        experience_level = input("Experience level (beginner/intermediate/advanced) [intermediate]: ").strip() or "intermediate"
        
        interests_input = input("Enter interests (comma-separated): ")
        interests = [i.strip() for i in interests_input.split(",")] if interests_input else []
        
        languages_input = input("Enter preferred languages (comma-separated): ")
        preferred_languages = [l.strip() for l in languages_input.split(",")] if languages_input else []
        
        time_input = input("Time availability (hours per week) [optional]: ").strip()
        time_availability = int(time_input) if time_input.isdigit() else None
        
        profile_data = {
            "skills": skills,
            "experience_level": experience_level,
            "interests": interests,
            "preferred_languages": preferred_languages,
            "time_availability_hours_per_week": time_availability,
        }
        
        try:
            create_profile_manual(profile_data)
        except Exception as e:
            print(f"Error creating profile: {e}")
    else:
        print("Please specify --github, --resume, or --manual")


def cmd_update_profile(args):
    """Update existing profile interactively."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    try:
        profile = load_dev_profile()
    except FileNotFoundError:
        print("Profile not found. Create one first with 'create-profile'.")
        return
    
    print("\n" + "=" * 80)
    print("UPDATE DEVELOPER PROFILE")
    print("=" * 80)
    print("\nCurrent profile:")
    print(json.dumps(profile, indent=2))
    print("\n" + "=" * 80)
    print("Enter new values (press Enter to keep current value)")
    print("=" * 80 + "\n")
    
    # Update skills
    current_skills = ", ".join(profile.get("skills", []))
    skills_input = input(f"Skills (current: {current_skills}): ").strip()
    if skills_input:
        profile["skills"] = [s.strip() for s in skills_input.split(",") if s.strip()]
    else:
        profile["skills"] = profile.get("skills", [])
    
    # Update experience level
    current_exp = profile.get("experience_level", "intermediate")
    exp_input = input(f"Experience level [beginner/intermediate/advanced] (current: {current_exp}): ").strip()
    if exp_input:
        if exp_input.lower() not in ["beginner", "intermediate", "advanced"]:
            print(f"Invalid experience level. Keeping current value: {current_exp}")
        else:
            profile["experience_level"] = exp_input.lower()
    else:
        profile["experience_level"] = current_exp
    
    # Update interests
    current_interests = ", ".join(profile.get("interests", []))
    interests_input = input(f"Interests (current: {current_interests}): ").strip()
    if interests_input:
        profile["interests"] = [i.strip() for i in interests_input.split(",") if i.strip()]
    else:
        profile["interests"] = profile.get("interests", [])
    
    # Update preferred languages
    current_langs = ", ".join(profile.get("preferred_languages", []))
    langs_input = input(f"Preferred languages (current: {current_langs}): ").strip()
    if langs_input:
        profile["preferred_languages"] = [l.strip() for l in langs_input.split(",") if l.strip()]
    else:
        profile["preferred_languages"] = profile.get("preferred_languages", [])
    
    # Update time availability
    current_time = profile.get("time_availability_hours_per_week")
    time_str = str(current_time) if current_time is not None else "None"
    time_input = input(f"Time availability (hours per week) (current: {time_str}): ").strip()
    if time_input:
        try:
            profile["time_availability_hours_per_week"] = int(time_input) if time_input.isdigit() else None
        except ValueError:
            print(f"Invalid number. Keeping current value: {time_str}")
            profile["time_availability_hours_per_week"] = current_time
    else:
        profile["time_availability_hours_per_week"] = current_time
    
    # Save updated profile
    try:
        save_dev_profile(profile)
        print("\n" + "=" * 80)
        print("Profile updated successfully!")
        print("=" * 80)
        print("\nUpdated profile:")
        print(json.dumps(profile, indent=2))
    except Exception as e:
        print(f"\nError saving profile: {e}")


def cmd_label_export(args):
    """Export unlabeled issues to CSV for manual labeling."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    issues = query_unlabeled_issues(
        difficulty=args.difficulty,
        limit=args.limit,
    )
    
    if not issues:
        print("No unlabeled issues found.")
        return
    
    # Try to load profile for scoring
    profile = None
    try:
        profile = load_dev_profile()
        print("Profile data loaded - calculating scores for issues...")
    except FileNotFoundError:
        print("Profile data not found - scores will be omitted")
    
    # Prepare issues for export
    export_data = []
    for issue in issues:
        issue_data = {
            'issue_id': issue.get('id'),
            'title': issue.get('title', ''),
            'repo_name': f"{issue.get('repo_owner', '')}/{issue.get('repo_name', '')}",
            'url': issue.get('url', ''),
            'difficulty': issue.get('difficulty', ''),
            'issue_type': issue.get('issue_type', ''),
            'time_estimate': issue.get('time_estimate', ''),
            'body': (issue.get('body', '') or '')[:500],
        }
        
        # Get technologies
        from contribution_matcher.database import get_issue_technologies
        techs = get_issue_technologies(issue.get('id'))
        issue_data['technologies'] = ', '.join([tech for tech, _ in techs])
        
        # Calculate score if profile available
        if profile:
            try:
                score_result = score_issue_against_profile(profile, issue)
                issue_data['current_score'] = score_result.get('score', 0)
            except Exception as e:
                issue_data['current_score'] = None
        else:
            issue_data['current_score'] = None
        
        # Add empty label column
        issue_data['label'] = ''
        
        export_data.append(issue_data)
    
    # Write to CSV
    if export_data:
        fieldnames = list(export_data[0].keys())
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_data)
        
        print(f"Exported {len(export_data)} unlabeled issues to {args.output}")
        print("Please fill in the 'label' column with 'good' or 'bad', then use 'label-import' to import labels.")
    else:
        print("No issues to export")


def cmd_label_import(args):
    """Import labels from CSV file."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    if not os.path.exists(args.input):
        print(f"Error: File {args.input} not found.")
        return
    
    success_count = 0
    error_count = 0
    errors = []
    
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        if 'issue_id' not in reader.fieldnames or 'label' not in reader.fieldnames:
            print("Error: CSV must contain 'issue_id' and 'label' columns.")
            return
        
        for row_num, row in enumerate(reader, start=2):
            issue_id_str = row.get('issue_id', '').strip()
            label = row.get('label', '').strip().lower()
            
            if not issue_id_str:
                errors.append(f"Row {row_num}: Missing issue_id")
                error_count += 1
                continue
            
            try:
                issue_id = int(issue_id_str)
            except ValueError:
                errors.append(f"Row {row_num}: Invalid issue_id '{issue_id_str}'")
                error_count += 1
                continue
            
            if not label:
                continue
            
            if label not in ['good', 'bad']:
                errors.append(f"Row {row_num}: Invalid label '{label}' (must be 'good' or 'bad')")
                error_count += 1
                continue
            
            if update_issue_label(issue_id, label):
                success_count += 1
            else:
                errors.append(f"Row {row_num}: Issue ID {issue_id} not found or update failed")
                error_count += 1
    
    print(f"\nImport complete:")
    print(f"  Successfully imported: {success_count} labels")
    print(f"  Errors: {error_count}")
    
    if errors and args.verbose:
        print("\nErrors:")
        for error in errors[:20]:
            print(f"  {error}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")


def cmd_label_status(args):
    """Show labeling progress and statistics."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    stats = get_labeling_statistics()
    
    print("\n" + "=" * 80)
    print("LABELING STATUS")
    print("=" * 80)
    
    print(f"\nTotal Issues: {stats['total_issues']}")
    print(f"Labeled Issues: {stats['labeled_issues']}")
    print(f"Unlabeled Issues: {stats['unlabeled_issues']}")
    print(f"\nGood Issues: {stats['good_issues']}")
    print(f"Bad Issues: {stats['bad_issues']}")
    
    print(f"\nProgress to 200 minimum: {stats['progress_to_200']:.1f}%")
    print(f"Remaining to reach 200: {stats['remaining_to_200']} issues")
    
    if stats['labeled_issues'] < 200:
        needed_good = max(0, 100 - stats['good_issues'])
        needed_bad = max(0, 100 - stats['bad_issues'])
        print(f"\nRecommended:")
        print(f"  - Need {needed_good} more 'good' labels")
        print(f"  - Need {needed_bad} more 'bad' labels")
    else:
        print("\nMinimum sample size (200) reached!")
        if not stats['is_balanced']:
            diff = abs(stats['good_issues'] - stats['bad_issues'])
            print(f"  Note: Labeling is unbalanced (difference: {diff} issues)")
        else:
            print("  Labeling is balanced")
    
    print("\n" + "=" * 80)


def cmd_train_model(args):
    """Train ML model on labeled issues."""
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    try:
        results = train_model(force=args.force)
        print("\nModel training completed successfully!")
        print(f"  Model accuracy: {results['accuracy']:.3f}")
        print(f"  Model saved. ML predictions will now be used in scoring.")
    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError training model: {e}")
        import traceback
        traceback.print_exc()


def cmd_stats(args):
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    stats = get_statistics()
    
    print("\n" + "=" * 80)
    print("CONTRIBUTION MATCHER STATISTICS")
    print("=" * 80)
    
    print(f"\nTotal Issues: {stats['total_issues']}")
    print(f"Issues in Last 7 Days: {stats['issues_last_7_days']}")
    print(f"Average Technologies per Issue: {stats['avg_technologies_per_issue']}")
    
    if stats.get('issues_by_difficulty'):
        print("\nIssues by Difficulty:")
        for difficulty, count in stats['issues_by_difficulty'].items():
            print(f"  {difficulty}: {count}")
    
    if stats.get('issues_by_type'):
        print("\nIssues by Type:")
        for issue_type, count in stats['issues_by_type'].items():
            print(f"  {issue_type}: {count}")
    
    if stats.get('top_technologies'):
        print("\nTop 20 Technologies:")
        for tech, count in list(stats['top_technologies'].items())[:20]:
            print(f"  {tech}: {count}")
    
    if stats.get('top_repos'):
        print("\nTop 20 Repositories:")
        for repo, count in list(stats['top_repos'].items())[:20]:
            print(f"  {repo}: {count}")
    
    print("\n" + "=" * 80)


def cmd_export(args):
    try:
        init_db()
    except Exception as e:
        print(f"Error creating database: {e}")
        return
    
    issues = query_issues(
        difficulty=args.difficulty,
        technology=args.technology,
        repo_owner=args.repo_owner,
        issue_type=args.issue_type,
        days_back=args.days_back,
        limit=args.limit,
    )
    
    if args.format.lower() == 'csv':
        export_to_csv(args.output, issues)
    elif args.format.lower() == 'json':
        export_to_json(args.output, issues)
    else:
        print(f"Unsupported format: {args.format}. Use 'csv' or 'json'.")


def main():
    """Main entry point with CLI interface."""
    parser = argparse.ArgumentParser(
        description="Contribution Matcher - Find and match GitHub issues to your skills"
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover new GitHub issues')
    discover_parser.add_argument('--labels', help='Comma-separated list of labels to search for')
    discover_parser.add_argument('--language', help='Filter by programming language')
    discover_parser.add_argument('--stars', type=int, help='Minimum repository stars')
    discover_parser.add_argument('--limit', type=int, help='Maximum number of issues to fetch')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List issues from database')
    list_parser.add_argument('--difficulty', help='Filter by difficulty')
    list_parser.add_argument('--technology', help='Filter by technology')
    list_parser.add_argument('--repo-owner', help='Filter by repository owner')
    list_parser.add_argument('--issue-type', help='Filter by issue type')
    list_parser.add_argument('--days-back', type=int, help='Only show issues from last N days')
    list_parser.add_argument('--limit', type=int, help='Maximum number of results')
    
    # Score command
    score_parser = subparsers.add_parser('score', help='Score profile against issues')
    score_parser.add_argument('--issue-id', type=int, help='Score against specific issue ID')
    score_parser.add_argument('--top', type=int, help='Show top N matches')
    score_parser.add_argument('--limit', type=int, help='Maximum number of issues to score')
    score_parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    score_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed breakdown')
    
    # Create profile command
    create_profile_parser = subparsers.add_parser('create-profile', help='Create developer profile')
    create_profile_parser.add_argument('--github', help='Import from GitHub username')
    create_profile_parser.add_argument('--resume', help='Import from resume PDF path')
    create_profile_parser.add_argument('--manual', action='store_true', help='Create profile manually')
    
    # Update profile command
    update_profile_parser = subparsers.add_parser('update-profile', help='Update existing profile')
    
    # Label export command
    label_export_parser = subparsers.add_parser('label-export', help='Export unlabeled issues to CSV')
    label_export_parser.add_argument('--output', required=True, help='Output CSV file path')
    label_export_parser.add_argument('--difficulty', help='Filter by difficulty')
    label_export_parser.add_argument('--limit', type=int, help='Maximum number of issues to export')
    
    # Label import command
    label_import_parser = subparsers.add_parser('label-import', help='Import labels from CSV file')
    label_import_parser.add_argument('--input', required=True, help='Input CSV file path with labels')
    label_import_parser.add_argument('--verbose', '-v', action='store_true', help='Show detailed error messages')
    
    # Label status command
    label_status_parser = subparsers.add_parser('label-status', help='Show labeling progress')
    
    # Train model command
    train_parser = subparsers.add_parser('train-model', help='Train ML model on labeled issues')
    train_parser.add_argument('--force', action='store_true', help='Train even if minimum sample size not met')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics about stored issues')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export issues to CSV or JSON')
    export_parser.add_argument('--format', choices=['csv', 'json'], default='csv', help='Export format')
    export_parser.add_argument('--output', required=True, help='Output file path')
    export_parser.add_argument('--difficulty', help='Filter by difficulty')
    export_parser.add_argument('--technology', help='Filter by technology')
    export_parser.add_argument('--repo-owner', help='Filter by repository owner')
    export_parser.add_argument('--issue-type', help='Filter by issue type')
    export_parser.add_argument('--days-back', type=int, help='Only export issues from last N days')
    export_parser.add_argument('--limit', type=int, help='Maximum number of results')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
    elif args.command == 'discover':
        cmd_discover(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'score':
        cmd_score(args)
    elif args.command == 'create-profile':
        cmd_create_profile(args)
    elif args.command == 'update-profile':
        cmd_update_profile(args)
    elif args.command == 'label-export':
        cmd_label_export(args)
    elif args.command == 'label-import':
        cmd_label_import(args)
    elif args.command == 'label-status':
        cmd_label_status(args)
    elif args.command == 'train-model':
        cmd_train_model(args)
    elif args.command == 'stats':
        cmd_stats(args)
    elif args.command == 'export':
        cmd_export(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

