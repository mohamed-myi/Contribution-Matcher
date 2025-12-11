"""
Contribution Matcher CLI.

Uses core repositories, ScoringService, Celery tasks, and unified database layer.
"""

import argparse
import csv
import json
import os

from dotenv import load_dotenv

from core.api import (
    batch_check_issue_status,
    batch_get_repo_metadata,
    search_issues,
)
from core.cache import CacheKeys, cache
from core.cli.db_helpers import (
    get_all_issue_urls,
    get_issue_technologies,
    get_labeling_statistics,
    get_statistics,
    get_variety_statistics,
    init_database,
    mark_issues_inactive,
    query_issues,
    query_unlabeled_issues,
    replace_issue_technologies,
    update_issue_label,
    upsert_issue,
)
from core.cli.formatters import format_output
from core.db import db
from core.parsing import analyze_job_text, parse_issue
from core.parsing.quality_checker import check_issue_quality
from core.profile import (
    create_profile_from_github,
    create_profile_from_resume,
    create_profile_manual,
    load_dev_profile,
    save_dev_profile,
)
from core.repositories import IssueRepository
from core.scoring import (
    get_top_matches,
    score_issue_against_profile,
    score_profile_against_all_issues,
    train_model,
)
from core.services import ScoringService

load_dotenv()


def _init_database():
    """Initialize database using ORM."""
    try:
        init_database()
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise


def cmd_discover(args):
    """Discover new GitHub issues."""
    _init_database()

    print(f"\n{'=' * 60}\nSearching for GitHub Issues\n{'=' * 60}\n")

    labels = None
    if args.labels:
        labels = args.labels.split(",")

    print("Searching GitHub for issues...")
    issues = search_issues(
        labels=labels, language=args.language, min_stars=args.stars, limit=args.limit or 100
    )
    print(f"Found {len(issues)} issues")

    repo_list = []
    issue_repo_map = {}
    for issue in issues:
        repo_url = issue.get("repository_url", "")
        if repo_url:
            parts = repo_url.replace("https://api.github.com/repos/", "").split("/")
            if len(parts) >= 2:
                repo_owner, repo_name = parts[0], parts[1]
                repo_key = (repo_owner, repo_name)
                if repo_key not in repo_list:
                    repo_list.append(repo_key)
                issue_repo_map[id(issue)] = repo_key

    if repo_list:
        if args.verbose:
            print(f"Fetching metadata for {len(repo_list)} repositories...")
        repo_metadata_batch = batch_get_repo_metadata(repo_list, use_cache=True, batch_size=10)
    else:
        repo_metadata_batch = {}

    new_count = 0
    for issue in issues:
        try:
            issue_id_obj = id(issue)
            repo_key = issue_repo_map.get(issue_id_obj)
            repo_metadata = repo_metadata_batch.get(repo_key) if repo_key else None

            is_valid, quality_issues = check_issue_quality(issue, repo_metadata)
            if not is_valid and not args.no_quality_filters:
                if args.verbose:
                    print(
                        f"Skipping issue {issue.get('html_url', 'unknown')}: {', '.join(quality_issues)}"
                    )
                continue

            parsed = parse_issue(issue, repo_metadata)
            issue_body = parsed.get("body", "") or ""
            category, technologies, keyword_counts = analyze_job_text(issue_body)
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

            replace_issue_technologies(issue_id, technologies)
            new_count += 1

        except Exception as e:
            print(f"Error processing issue {issue.get('html_url', 'unknown')}: {e}")
            continue

    print(f"\n{'=' * 60}")
    print(f"Search complete: Processed {new_count} issues")
    print(f"{'=' * 60}\n")


def cmd_discover_async(args):
    """Discover issues asynchronously using Celery."""
    try:
        from workers.tasks import batch_discover_task, discover_issues_task

        print("Queuing async discovery task...")

        if args.batch:
            # Run multiple strategies
            task = batch_discover_task.delay(
                user_id=1,  # CLI uses default user
                strategies=None,  # Use defaults
            )
        else:
            labels = args.labels.split(",") if args.labels else None
            task = discover_issues_task.delay(
                user_id=1,
                labels=labels,
                language=args.language,
                limit=args.limit or 50,
            )

        print(f"Task queued: {task.id}")
        print("Use 'python main.py task-status --id {task.id}' to check status")

    except ImportError:
        print("Error: Celery workers not available.")
        print("Start workers with: celery -A workers worker --loglevel=info")
        print("Or use synchronous discovery: python main.py discover")


def cmd_task_status(args):
    """Check status of a Celery task."""
    try:
        from workers.celery_app import celery_app

        result = celery_app.AsyncResult(args.id)

        print(f"\nTask ID: {args.id}")
        print(f"Status: {result.status}")

        if result.ready():
            if result.successful():
                print(f"Result: {json.dumps(result.result, indent=2)}")
            else:
                print(f"Error: {result.result}")
        else:
            print("Task is still running...")

    except ImportError:
        print("Error: Celery not available")


def cmd_list(args):
    """List issues from database."""
    _init_database()

    issues = query_issues(
        difficulty=getattr(args, "difficulty", None),
        issue_type=getattr(args, "issue_type", None),
        limit=getattr(args, "limit", 100),
    )

    if not issues:
        print("No issues found matching the criteria.")
        return

    # Use formatter if format is specified
    output_format = getattr(args, "format", "text")
    try:
        if isinstance(output_format, str):
            output_format = output_format.lower()
        elif output_format:
            output_format = str(output_format).lower()
        else:
            output_format = "text"
    except Exception:
        output_format = "text"

    verbose = getattr(args, "verbose", False)

    if output_format and output_format != "text":
        try:
            output = format_output(
                issues, output_format, verbose=verbose, output_file=getattr(args, "output", None)
            )
            if output:
                print(output)
                return
        except Exception as e:
            if verbose:
                print(f"Warning: Format error ({e}), using default text output")
            output_format = "text"

    # Default text output
    if verbose:
        print(f"\nFound {len(issues)} issue(s):\n")
        print("=" * 80)
        for issue in issues:
            print(f"\nTitle: {issue.get('title', 'N/A')}")
            if issue.get("repo_name"):
                print(f"Repository: {issue.get('repo_owner', '')}/{issue.get('repo_name', '')}")
            if issue.get("difficulty"):
                print(f"Difficulty: {issue['difficulty']}")
            if issue.get("issue_type"):
                print(f"Type: {issue['issue_type']}")
            if issue.get("time_estimate"):
                print(f"Time Estimate: {issue['time_estimate']}")
            if issue.get("repo_stars"):
                print(f"Stars: {issue['repo_stars']}")
            print(f"URL: {issue.get('url', 'N/A')}")
            print(f"Created: {issue.get('created_at', 'N/A')}")
            print("-" * 80)
    else:
        print(f"Found {len(issues)} issue(s)")
        for i, issue in enumerate(issues[:10], 1):
            print(f"{i}. {issue.get('title', 'N/A')} - {issue.get('url', 'N/A')}")
        if len(issues) > 10:
            print(f"... and {len(issues) - 10} more")


def cmd_score(args):
    """Score profile against issues using ScoringService."""
    _init_database()

    # Load profile
    try:
        profile = load_dev_profile()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Run 'python main.py create-profile' first.")
        return

    if args.use_cache:
        # Use new ScoringService with caching
        print("Using cached scoring service...")
        try:
            with db.session() as session:
                issue_repo = IssueRepository(session)
                ScoringService(issue_repo)

                if args.top:
                    # Get top matches using cached service
                    # Note: This requires a user_id, so we use a placeholder
                    print("Note: Cached scoring requires API authentication.")
                    print("Falling back to standard scoring...")
        except Exception as e:
            print(f"Cache error: {e}, using standard scoring...")

    # Standard scoring (legacy)
    if args.issue_id:
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
        _print_score_result(score_result, args.format == "json", verbose=args.verbose)
    else:
        if args.top:
            scores = get_top_matches(profile=profile, limit=args.top)
        else:
            scores = score_profile_against_all_issues(profile=profile, limit=args.limit)

        if args.format == "json":
            print(json.dumps(scores, indent=2))
        else:
            _print_score_results(scores, args.verbose)


def cmd_score_async(args):
    """Trigger background scoring using Celery."""
    try:
        from workers.tasks import score_user_issues_task

        print("Queuing scoring task...")
        task = score_user_issues_task.delay(user_id=1)  # CLI uses default user

        print(f"Task queued: {task.id}")
        print("Use 'python main.py task-status --id {task.id}' to check status")

    except ImportError:
        print("Error: Celery workers not available.")
        print("Use synchronous scoring: python main.py score")


def _generate_recommendations(breakdown: dict, issue_data: dict) -> list[str]:
    """Generate actionable recommendations based on score breakdown."""
    recommendations = []
    skills = breakdown.get("skills", {})
    experience = breakdown.get("experience", {})
    repo_quality = breakdown.get("repo_quality", {})
    time_match = breakdown.get("time_match", {})

    missing_skills = skills.get("missing", [])
    if missing_skills:
        top_missing = missing_skills[:3]
        recommendations.append(f"Learn {', '.join(top_missing)} to improve skill match")

    profile_level = experience.get("profile_level", "").lower()
    issue_difficulty = experience.get("issue_difficulty", "").lower()
    if profile_level == "beginner" and issue_difficulty == "advanced":
        recommendations.append("Consider starting with intermediate issues to build experience")
    elif profile_level == "advanced" and issue_difficulty == "beginner":
        recommendations.append("This issue may be too simple for your experience level")

    time_score = time_match.get("score", 0)
    if time_score < 5:
        recommendations.append(
            "Time estimate may exceed your availability - consider smaller issues"
        )

    stars = repo_quality.get("stars", 0) or 0
    if stars < 10:
        recommendations.append("Repository has low activity - verify it's actively maintained")

    return recommendations


def _calculate_confidence(breakdown: dict) -> str:
    """Calculate confidence level based on score components."""
    skills_pct = breakdown.get("skills", {}).get("match_percentage", 0)
    ml_pred = breakdown.get("ml_prediction", {})
    ml_good_prob = ml_pred.get("good_probability", 0.5)

    if skills_pct >= 80 and ml_good_prob >= 0.7:
        return "High"
    elif skills_pct >= 60 and ml_good_prob >= 0.6:
        return "Medium"
    elif skills_pct >= 40:
        return "Low-Medium"
    else:
        return "Low"


def _print_score_result(score_result: dict, json_format: bool = False, verbose: bool = False):
    if json_format:
        print(json.dumps(score_result, indent=2))
        return

    print("\n" + "=" * 80)
    print(f"Issue: {score_result['issue_title']}")
    if score_result.get("repo_name"):
        print(f"Repository: {score_result['repo_name']}")
    print(f"URL: {score_result['url']}")

    score = score_result["score"]
    breakdown = score_result["breakdown"]
    confidence = _calculate_confidence(breakdown)

    print(f"\nMatch Score: {score}/100 (Confidence: {confidence})")
    print("-" * 80)

    skills = breakdown["skills"]
    print(f"\nSkills Match: {skills['match_percentage']:.1f}%")
    if verbose:
        print(f"  Matching: {', '.join(skills['matching'][:10])}")
        if skills["missing"]:
            print(f"  Missing: {', '.join(skills['missing'][:10])}")

    exp = breakdown["experience"]
    print(f"\nExperience Score: {exp['score']:.1f}/20")
    if verbose:
        print(f"  Profile: {exp.get('profile_level', 'N/A')}")
        print(f"  Issue difficulty: {exp.get('issue_difficulty', 'N/A')}")

    repo_quality = breakdown["repo_quality"]
    print(f"\nRepo Quality Score: {repo_quality['score']:.1f}/15")
    if verbose:
        print(f"  Stars: {repo_quality.get('stars', 'N/A')}")
        print(f"  Forks: {repo_quality.get('forks', 'N/A')}")

    print("=" * 80)


def _print_score_results(scores: list[dict], verbose: bool = False):
    if not scores:
        print("No issues found to score against.")
        return

    print(f"\n{'=' * 80}")
    print(f"ISSUE SCORING RESULTS - Top {len(scores)} Matches")
    print(f"{'=' * 80}\n")

    for i, score_result in enumerate(scores, 1):
        print(f"{i}. {score_result['issue_title']}")
        if score_result.get("repo_name"):
            print(f"   Repository: {score_result['repo_name']}")
        print(f"   Score: {score_result['score']}/100")
        print(f"   URL: {score_result['url']}")

        if verbose:
            breakdown = score_result["breakdown"]
            skills = breakdown["skills"]
            print(f"   Skills: {skills['match_percentage']:.1f}% match")
            if skills["missing"]:
                print(f"   Missing: {', '.join(skills['missing'][:5])}")

        print()


def cmd_create_profile(args):
    """Create developer profile."""
    _init_database()

    not getattr(args, "no_encrypt", False)

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
        print("Creating profile manually...")
        skills_input = input("Enter skills (comma-separated): ")
        skills = [s.strip() for s in skills_input.split(",")] if skills_input else []

        experience_level = (
            input("Experience level (beginner/intermediate/advanced) [intermediate]: ").strip()
            or "intermediate"
        )

        interests_input = input("Enter interests (comma-separated): ")
        interests = [i.strip() for i in interests_input.split(",")] if interests_input else []

        languages_input = input("Enter preferred languages (comma-separated): ")
        preferred_languages = (
            [lang.strip() for lang in languages_input.split(",")] if languages_input else []
        )

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
    """Update existing profile."""
    _init_database()

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

    # Update experience level
    current_exp = profile.get("experience_level", "intermediate")
    exp_input = input(
        f"Experience level [beginner/intermediate/advanced] (current: {current_exp}): "
    ).strip()
    if exp_input and exp_input.lower() in ["beginner", "intermediate", "advanced"]:
        profile["experience_level"] = exp_input.lower()

    # Update interests
    current_interests = ", ".join(profile.get("interests", []))
    interests_input = input(f"Interests (current: {current_interests}): ").strip()
    if interests_input:
        profile["interests"] = [i.strip() for i in interests_input.split(",") if i.strip()]

    # Update preferred languages
    current_langs = ", ".join(profile.get("preferred_languages", []))
    langs_input = input(f"Preferred languages (current: {current_langs}): ").strip()
    if langs_input:
        profile["preferred_languages"] = [
            lang.strip() for lang in langs_input.split(",") if lang.strip()
        ]

    # Update time availability
    current_time = profile.get("time_availability_hours_per_week")
    time_str = str(current_time) if current_time is not None else "None"
    time_input = input(f"Time availability (hours per week) (current: {time_str}): ").strip()
    if time_input and time_input.isdigit():
        profile["time_availability_hours_per_week"] = int(time_input)

    # Save updated profile
    try:
        encrypt = not getattr(args, "no_encrypt", False)
        save_dev_profile(profile, encrypt=encrypt)
        print("\n" + "=" * 80)
        print("Profile updated successfully!")
        print("=" * 80)
    except Exception as e:
        print(f"\nError saving profile: {e}")


def cmd_label_export(args):
    """Export unlabeled issues to CSV for manual labeling."""
    _init_database()

    issues = query_unlabeled_issues(limit=getattr(args, "limit", 100))

    if not issues:
        print("No unlabeled issues found.")
        return

    profile = None
    try:
        profile = load_dev_profile()
        print("Profile loaded - calculating scores...")
    except (FileNotFoundError, ImportError):
        print("Profile not found - scores will be omitted")

    export_data = []
    for issue in issues:
        issue_data = {
            "issue_id": issue.get("id"),
            "title": issue.get("title", ""),
            "repo_name": f"{issue.get('repo_owner', '')}/{issue.get('repo_name', '')}",
            "url": issue.get("url", ""),
            "difficulty": issue.get("difficulty", ""),
            "issue_type": issue.get("issue_type", ""),
            "time_estimate": issue.get("time_estimate", ""),
            "body": (issue.get("body", "") or "")[:500],
        }

        techs = get_issue_technologies(issue.get("id"))
        issue_data["technologies"] = ", ".join([tech for tech, _ in techs])

        if profile:
            try:
                score_result = score_issue_against_profile(profile, issue)
                issue_data["current_score"] = score_result.get("score", 0)
            except Exception:
                issue_data["current_score"] = None
        else:
            issue_data["current_score"] = None

        issue_data["label"] = ""
        export_data.append(issue_data)

    if export_data:
        fieldnames = list(export_data[0].keys())
        with open(args.output, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(export_data)

        print(f"Exported {len(export_data)} unlabeled issues to {args.output}")
        print("Fill in 'label' column with 'good' or 'bad', then use 'label-import'.")


def cmd_label_import(args):
    """Import labels from CSV file."""
    _init_database()

    if not os.path.exists(args.input):
        print(f"Error: File {args.input} not found.")
        return

    success_count = 0
    error_count = 0
    errors = []

    with open(args.input, encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if "issue_id" not in reader.fieldnames or "label" not in reader.fieldnames:
            print("Error: CSV must contain 'issue_id' and 'label' columns.")
            return

        for row_num, row in enumerate(reader, start=2):
            issue_id_str = row.get("issue_id", "").strip()
            label = row.get("label", "").strip().lower()

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

            if label not in ["good", "bad"]:
                errors.append(f"Row {row_num}: Invalid label '{label}'")
                error_count += 1
                continue

            if update_issue_label(issue_id, label):
                success_count += 1
            else:
                errors.append(f"Row {row_num}: Issue ID {issue_id} not found")
                error_count += 1

    print(f"\nImport complete: {success_count} labels imported, {error_count} errors")
    if errors and args.verbose:
        for error in errors[:20]:
            print(f"  {error}")


def cmd_label_status(args):
    """Show labeling progress."""
    _init_database()

    stats = get_labeling_statistics()
    all_stats = get_statistics()

    total_issues = all_stats.get("total_issues", 0)
    total_labeled = stats.get("total_labeled", 0)
    by_label = stats.get("by_label", {})
    good_issues = by_label.get("good", 0)
    bad_issues = by_label.get("bad", 0)
    unlabeled = total_issues - total_labeled
    progress = (total_labeled / 200.0) * 100 if total_labeled < 200 else 100.0

    print("\n" + "=" * 80)
    print("LABELING STATUS")
    print("=" * 80)
    print(f"\nTotal Issues: {total_issues}")
    print(f"Labeled: {total_labeled} | Unlabeled: {unlabeled}")
    print(f"Good: {good_issues} | Bad: {bad_issues}")
    print(f"\nProgress to 200: {progress:.1f}%")
    print("=" * 80)


def cmd_train_model(args):
    """Train ML model on labeled issues."""
    _init_database()

    try:
        results = train_model(
            force=args.force,
            use_advanced=not args.no_advanced,
            use_stacking=not args.no_stacking,
            use_tuning=not args.no_tune,
            tune_iterations=args.tune_iterations,
            legacy=args.legacy,
        )
        print("\nModel training completed!")
        print(f"  Accuracy: {results['accuracy']:.3f}")
        print(f"  Recall: {results['recall']:.3f}")

        # Invalidate model cache
        try:
            scoring_service = ScoringService()
            scoring_service.invalidate_model_cache()
            print("  Model cache invalidated")
        except Exception:
            pass

    except ValueError as e:
        print(f"\nError: {e}")
    except Exception as e:
        print(f"\nError training model: {e}")


def cmd_train_async(args):
    """Train ML model asynchronously using Celery."""
    try:
        from workers.tasks import train_model_task

        print("Queuing ML training task...")
        task = train_model_task.delay(
            model_type="xgboost" if not args.legacy else "gradient_boosting",
            use_hyperopt=not args.no_tune,
        )

        print(f"Task queued: {task.id}")
        print("Training may take 10-30 minutes.")
        print("Use 'python main.py task-status --id {task.id}' to check status")

    except ImportError:
        print("Error: Celery workers not available.")
        print("Use synchronous training: python main.py train-model")


def cmd_stats(args):
    """Show statistics about stored issues."""
    _init_database()

    stats = get_statistics()

    print("\n" + "=" * 80)
    print("CONTRIBUTION MATCHER STATISTICS")
    print("=" * 80)
    print(f"\nTotal Issues: {stats.get('total_issues', 0)}")
    print(f"Active Issues: {stats.get('active_issues', 0)}")
    print(f"Labeled Issues: {stats.get('labeled_issues', 0)}")

    if stats.get("by_difficulty"):
        print("\nBy Difficulty:")
        for d, c in stats["by_difficulty"].items():
            if d:  # Skip None key
                print(f"  {d}: {c}")

    print("=" * 80)


def cmd_variety_stats(args):
    """Show variety statistics."""
    _init_database()

    stats = get_variety_statistics()

    print("\n" + "=" * 80)
    print("ISSUE VARIETY STATISTICS")
    print("=" * 80)
    print(
        f"\nActive: {stats.get('active_issues', 0)} | Inactive: {stats.get('inactive_issues', 0)}"
    )
    print(f"Last 30 Days: {stats.get('issues_last_30_days', 0)}")

    if stats.get("languages"):
        print("\nTop Languages:")
        for lang, count in list(stats["languages"].items())[:10]:
            print(f"  {lang}: {count}")

    print("=" * 80)


def cmd_cleanup_stale(args):
    """Check and mark closed issues as inactive."""
    _init_database()

    print("\n" + "=" * 80)
    print("CLEANING UP STALE ISSUES")
    print("=" * 80 + "\n")

    urls = get_all_issue_urls()
    print(f"Found {len(urls)} active issues")

    if not urls:
        return

    batch_size = args.limit if hasattr(args, "limit") and args.limit else 50
    urls_to_check = urls[:batch_size]

    print(f"Checking {len(urls_to_check)} issues...")
    statuses = batch_check_issue_status(urls_to_check)

    closed_urls = [url for url, status in statuses.items() if status == "closed"]

    if closed_urls:
        updated = mark_issues_inactive(closed_urls)
        print(f"Marked {updated} issues as inactive")

    print(f"\nOpen: {sum(1 for s in statuses.values() if s == 'open')}")
    print(f"Closed: {len(closed_urls)}")
    print("=" * 80)


def cmd_cache_status(args):
    """Show cache status and health."""
    cache.initialize()

    print("\n" + "=" * 80)
    print("CACHE STATUS")
    print("=" * 80)

    health = cache.health_check()
    print(f"\nRedis Available: {health.get('available', False)}")
    print(f"Status: {health.get('status', 'unknown')}")

    if health.get("available"):
        print(f"Memory Used: {health.get('memory_used', 'unknown')}")
        print(f"Connected Clients: {health.get('connected_clients', 0)}")

    print("=" * 80)


def cmd_cache_clear(args):
    """Clear cache for a user or all."""
    cache.initialize()

    if args.all:
        if input("Clear ALL cache? (y/N): ").lower() == "y":
            cache.flush_all()
            print("All cache cleared")
    elif args.user_id:
        deleted = cache.delete_pattern(CacheKeys.user_pattern(args.user_id))
        print(f"Cleared {deleted} cache entries for user {args.user_id}")
    elif args.models:
        deleted = cache.delete_pattern(CacheKeys.ml_pattern())
        print(f"Cleared {deleted} model cache entries")
    else:
        print("Specify --all, --user-id, or --models")


def cmd_export(args):
    """Export issues to CSV or JSON."""
    _init_database()

    issues = query_issues(
        difficulty=getattr(args, "difficulty", None),
        issue_type=getattr(args, "issue_type", None),
        limit=getattr(args, "limit", 1000),
    )

    if args.format.lower() in ["csv", "excel"]:
        format_output(
            issues,
            args.format.lower(),
            verbose=getattr(args, "verbose", False),
            output_file=args.output,
        )
        print(f"Exported {len(issues)} issues to {args.output}")
    elif args.format.lower() == "json":
        import json

        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(issues, f, indent=2, default=str)
        print(f"Exported {len(issues)} issues to {args.output}")
    elif args.format.lower() in ["markdown", "html"]:
        output = format_output(issues, args.format.lower(), verbose=getattr(args, "verbose", False))
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Exported {len(issues)} issues to {args.output}")
    else:
        print(f"Unsupported format: {args.format}")


def main():
    """Main entry point with CLI interface."""
    parser = argparse.ArgumentParser(
        description="Contribution Matcher - Find and match GitHub issues to your skills"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Discover command
    discover_parser = subparsers.add_parser("discover", help="Discover new GitHub issues")
    discover_parser.add_argument("--labels", help="Comma-separated list of labels")
    discover_parser.add_argument("--language", help="Filter by programming language")
    discover_parser.add_argument("--stars", type=int, help="Minimum repository stars")
    discover_parser.add_argument("--limit", type=int, help="Maximum number of issues")
    discover_parser.add_argument(
        "--no-quality-filters", action="store_true", help="Disable quality filters"
    )
    discover_parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    # Async discover command
    discover_async_parser = subparsers.add_parser(
        "discover-async", help="Discover issues asynchronously (Celery)"
    )
    discover_async_parser.add_argument("--labels", help="Comma-separated list of labels")
    discover_async_parser.add_argument("--language", help="Filter by programming language")
    discover_async_parser.add_argument("--limit", type=int, help="Maximum number of issues")
    discover_async_parser.add_argument(
        "--batch", action="store_true", help="Run multiple strategies"
    )

    # Task status command
    task_status_parser = subparsers.add_parser("task-status", help="Check Celery task status")
    task_status_parser.add_argument("--id", required=True, help="Task ID")

    # List command
    list_parser = subparsers.add_parser("list", help="List issues from database")
    list_parser.add_argument("--difficulty", help="Filter by difficulty")
    list_parser.add_argument("--technology", help="Filter by technology")
    list_parser.add_argument("--repo-owner", help="Filter by repository owner")
    list_parser.add_argument("--issue-type", help="Filter by issue type")
    list_parser.add_argument("--days-back", type=int, help="Only show issues from last N days")
    list_parser.add_argument("--limit", type=int, help="Maximum number of results")
    list_parser.add_argument(
        "--format",
        choices=["text", "json", "table", "csv", "excel", "markdown", "html"],
        default="text",
    )
    list_parser.add_argument("--output", "-o", help="Output file")
    list_parser.add_argument("--verbose", "-v", action="store_true")

    # Score command
    score_parser = subparsers.add_parser("score", help="Score profile against issues")
    score_parser.add_argument("--issue-id", type=int, help="Score against specific issue ID")
    score_parser.add_argument("--top", type=int, help="Show top N matches")
    score_parser.add_argument("--limit", type=int, help="Maximum number of issues to score")
    score_parser.add_argument("--format", choices=["text", "json"], default="text")
    score_parser.add_argument("--use-cache", action="store_true", help="Use cached scoring service")
    score_parser.add_argument("--verbose", "-v", action="store_true")

    # Score async command
    subparsers.add_parser("score-async", help="Score issues asynchronously (Celery)")

    # Profile commands
    create_profile_parser = subparsers.add_parser("create-profile", help="Create developer profile")
    create_profile_parser.add_argument("--github", help="Import from GitHub username")
    create_profile_parser.add_argument("--resume", help="Import from resume PDF")
    create_profile_parser.add_argument("--manual", action="store_true", help="Create manually")
    create_profile_parser.add_argument("--no-encrypt", action="store_true")

    update_profile_parser = subparsers.add_parser("update-profile", help="Update existing profile")
    update_profile_parser.add_argument("--no-encrypt", action="store_true")

    # Labeling commands
    label_export_parser = subparsers.add_parser("label-export", help="Export unlabeled issues")
    label_export_parser.add_argument("--output", required=True, help="Output CSV file")
    label_export_parser.add_argument("--difficulty", help="Filter by difficulty")
    label_export_parser.add_argument("--limit", type=int, help="Maximum issues")

    label_import_parser = subparsers.add_parser("label-import", help="Import labels from CSV")
    label_import_parser.add_argument("--input", required=True, help="Input CSV file")
    label_import_parser.add_argument("--verbose", "-v", action="store_true")

    subparsers.add_parser("label-status", help="Show labeling progress")

    # Training commands
    train_parser = subparsers.add_parser("train-model", help="Train ML model")
    train_parser.add_argument("--force", action="store_true")
    train_parser.add_argument("--no-tune", action="store_true")
    train_parser.add_argument("--no-stacking", action="store_true")
    train_parser.add_argument("--no-advanced", action="store_true")
    train_parser.add_argument("--legacy", action="store_true")
    train_parser.add_argument("--tune-iterations", type=int, default=50)

    train_async_parser = subparsers.add_parser("train-async", help="Train ML model asynchronously")
    train_async_parser.add_argument("--legacy", action="store_true")
    train_async_parser.add_argument("--no-tune", action="store_true")

    # Stats commands
    subparsers.add_parser("stats", help="Show statistics")
    subparsers.add_parser("variety-stats", help="Show variety statistics")

    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup-stale", help="Mark closed issues as inactive")
    cleanup_parser.add_argument("--limit", type=int, default=50)

    # Cache commands
    subparsers.add_parser("cache-status", help="Show cache status")
    cache_clear_parser = subparsers.add_parser("cache-clear", help="Clear cache")
    cache_clear_parser.add_argument("--all", action="store_true", help="Clear all cache")
    cache_clear_parser.add_argument("--user-id", type=int, help="Clear cache for user")
    cache_clear_parser.add_argument("--models", action="store_true", help="Clear model cache")

    # Export command
    export_parser = subparsers.add_parser("export", help="Export issues")
    export_parser.add_argument(
        "--format", choices=["csv", "json", "excel", "markdown", "html"], default="csv"
    )
    export_parser.add_argument("--output", required=True)
    export_parser.add_argument("--difficulty", help="Filter by difficulty")
    export_parser.add_argument("--technology", help="Filter by technology")
    export_parser.add_argument("--repo-owner", help="Filter by repo owner")
    export_parser.add_argument("--issue-type", help="Filter by issue type")
    export_parser.add_argument("--days-back", type=int)
    export_parser.add_argument("--limit", type=int)
    export_parser.add_argument("--verbose", "-v", action="store_true")

    args = parser.parse_args()

    commands = {
        "discover": cmd_discover,
        "discover-async": cmd_discover_async,
        "task-status": cmd_task_status,
        "list": cmd_list,
        "score": cmd_score,
        "score-async": cmd_score_async,
        "create-profile": cmd_create_profile,
        "update-profile": cmd_update_profile,
        "label-export": cmd_label_export,
        "label-import": cmd_label_import,
        "label-status": cmd_label_status,
        "train-model": cmd_train_model,
        "train-async": cmd_train_async,
        "stats": cmd_stats,
        "variety-stats": cmd_variety_stats,
        "cleanup-stale": cmd_cleanup_stale,
        "cache-status": cmd_cache_status,
        "cache-clear": cmd_cache_clear,
        "export": cmd_export,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
