# Contribution Matcher

An automated system that discovers GitHub issues, extracts structured data, matches them to your developer skills, and recommends the best contribution opportunities using hybrid scoring (rules + ML).

## Overview

This system automates the process of finding open source contribution opportunities by:
- Searching GitHub API for issues with labels like "good first issue", "help wanted", "beginner friendly"
- Extracting structured data (technologies, difficulty, time estimate, issue type)
- Storing issues in a SQLite database with technology categorization
- Scoring issues against your developer profile using rule-based and ML-enhanced algorithms
- Training ML models on manually labeled data to improve scoring accuracy

## Features

- **Automated Issue Discovery**: Searches GitHub for contribution opportunities
- **Intelligent Data Extraction**: Extracts technologies, difficulty, time estimates, and issue types
- **Profile Matching**: Scores issues against your skills, experience, and interests
- **ML-Enhanced Scoring**: Trainable machine learning model that learns from your preferences
- **Database Query Tools**: Query, filter, and export issue data
- **CLI Interface**: Comprehensive command-line interface for all operations

## Requirements

- Python 3.8+
- GitHub Personal Access Token
- SQLite (included with Python)

## Installation

1. Clone or create the project directory:
```bash
cd contribution_matcher
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
Create a `.env` file in the project root:
```
GITHUB_TOKEN=your_github_personal_access_token
CONTRIBUTION_MATCHER_DB_PATH=contribution_matcher.db  # Optional
```

**GitHub Token Setup:**
- Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
- Generate token with scopes: `public_repo`, `read:user`, `read:org` (if needed)
- Token is required for authenticated API access (5000 requests/hour vs 60/hour unauthenticated)

## Usage

### Basic Commands

**Discover new issues:**
```bash
python main.py discover --limit 100
```

**List issues from database:**
```bash
python main.py list --difficulty beginner --limit 10
```

**View statistics:**
```bash
python main.py stats
```

**Export issues:**
```bash
python main.py export --format csv --output issues.csv
```

### Profile Management

**Create profile from GitHub:**
```bash
python main.py create-profile --github your-username
```

**Create profile from resume:**
```bash
python main.py create-profile --resume path/to/resume.pdf
```

**Create profile manually:**
```bash
python main.py create-profile --manual
```

**Update existing profile:**
```bash
python main.py update-profile
```

**Update existing profile:**
```bash
python contribution_matcher.py update-profile
```
This will interactively prompt you to update each profile field (skills, experience level, interests, preferred languages, time availability).

### Issue Scoring

**Score issues against profile:**
```bash
# Score all issues
python main.py score

# Score top 10 matches
python main.py score --top 10

# Score specific issue
python main.py score --issue-id 123

# Show detailed breakdown
python main.py score --top 5 --verbose
```

### Machine Learning Training

The system includes ML-enhanced scoring that learns from your issue preferences. To train the model:

**1. Export issues for labeling:**
```bash
python main.py label-export --output issues_to_label.csv --limit 250
```

**2. Label issues in CSV:**
Open the CSV file and add `good` or `bad` in the `label` column:
- `good`: Issues you would contribute to
- `bad`: Issues you would not contribute to

**3. Import labels:**
```bash
python main.py label-import --input issues_to_label.csv
```

**4. Check progress:**
```bash
python main.py label-status
```

**5. Train model (after 200+ labels):**
```bash
python main.py train-model
```

**Training Requirements:**
- Minimum: 10 labeled issues (absolute minimum, model will be less accurate)
- Recommended: 200+ labeled issues (100+ good, 100+ bad) for optimal performance
- Need both "good" and "bad" labels (can't train with only one class)
- Profile data (`dev_profile.json`) improves feature quality but is optional

## Technical Architecture

### Core Components

**`contribution_matcher/cli/contribution_matcher.py`**: Main CLI interface
- Manages issue discovery workflow
- Provides CLI commands for all operations

**`contribution_matcher/api/github_api.py`**: GitHub API integration
- Searches for issues with specified criteria
- Fetches repository metadata
- Handles rate limiting and caching

**`contribution_matcher/parsing/issue_parser.py`**: Structured data extraction
- Extracts difficulty from labels and text
- Parses technologies from issue body, repo languages, and topics
- Extracts time estimates and classifies issue types

**`contribution_matcher/parsing/skill_extractor.py`**: Technology analysis and categorization
- Categorizes technologies into 8 categories
- Extracts 200+ technical skills

**`contribution_matcher/database/database.py`**: Database operations
- SQLite database management
- Schema initialization
- Issue and technology storage

**`contribution_matcher/database/database_queries.py`**: Query utilities
- Filter issues by difficulty, technology, repo, date range
- Aggregate statistics and analytics
- Export to CSV/JSON

**`contribution_matcher/profile/dev_profile.py`**: Developer profile management
- Creates profiles from GitHub, resume, or manual input
- Saves structured data to JSON and database

**`contribution_matcher/scoring/issue_scorer.py`**: Profile-to-issue matching
- Calculates match scores (0-100) using weighted factors
- Integrates ML predictions for enhanced accuracy
- Provides detailed breakdowns of matches

**`contribution_matcher/scoring/ml_trainer.py`**: Machine learning module
- Feature extraction from issues and profile data
- GradientBoosting classifier training
- Model evaluation and persistence
- Prediction functions for scoring adjustments

### Scoring Algorithm

The scoring system uses a hybrid approach combining rule-based and ML predictions:

**Rule-Based Scoring:**
- Skill match: 40 points
- Experience match: 20 points
- Repo quality: 15 points
- Freshness: 10 points
- Time match: 10 points
- Interest match: 5 points

**ML Adjustment (30% weight):**
- ML model predicts issue quality (good/bad probability)
- High-confidence "good" predictions boost scores
- High-confidence "bad" predictions reduce scores
- Raw adjustment range: -15 to +15 points
- Final adjustment after 30% weighting: -4.5 to +4.5 points

Final score is clamped to 0-100 range.

### Database Schema

**`issues` table:**
- `id`, `title`, `url` (UNIQUE), `body`
- `repo_owner`, `repo_name`, `repo_url`
- `difficulty`, `issue_type`, `time_estimate`, `labels` (JSON)
- `repo_stars`, `repo_forks`, `repo_languages` (JSON), `repo_topics` (JSON)
- `last_commit_date`, `contributor_count`, `is_active`
- `created_at`, `updated_at`, `label`, `labeled_at`

**`issue_technologies` table:**
- `id`, `issue_id` (FK), `technology`, `technology_category`

**`repo_metadata` table:**
- Cached repository information to reduce API calls

**`dev_profile` table:**
- Developer profile data (skills, experience, interests, etc.)

### ML Model Features

The ML model extracts 15 features focused on issue relevance:

1. Number of technologies required
2. Skill match percentage
3. Experience match score
4. Repo quality score
5. Issue freshness score
6. Time match score
7. Interest match score
8. Total rule-based score
9. Repo stars (normalized)
10. Repo forks (normalized)
11. Contributor count (normalized)
12. Issue type encoded
13. Difficulty encoded
14. Time estimate hours
15. Number of labels

## File Structure

```
contribution_matcher/
├── contribution_matcher/   # Main package
│   ├── api/                # GitHub API integration
│   ├── parsing/            # Issue parsing and data extraction
│   ├── scoring/            # Issue scoring and ML training
│   ├── database/           # Database operations
│   ├── profile/            # Profile management
│   ├── cli/                # CLI interface
│   └── config.py           # Configuration
├── main.py                 # Entry point
├── requirements.txt        # Dependencies
├── contribution_matcher.db # SQLite database
├── dev_profile.json        # Parsed profile data
├── issue_classifier.pkl    # Trained ML model
├── issue_scaler.pkl        # Feature scaler
├── tests/                  # Test suite
└── docs/                   # Documentation
```

## Workflow

### Issue Discovery

1. System searches GitHub API for new issues with specified labels
2. Extracts structured data (technologies, difficulty, time estimates, etc.)
3. Stores issues in database with technology categorization
4. Scores issues against profile (if profile data exists)

### ML Training Workflow

1. Export unlabeled issues to CSV
2. Manually label issues as "good" or "bad"
3. Import labels into database
4. Check progress toward 200-issue minimum
5. Train model when sufficient labels collected
6. Model automatically adjusts scores in future searches

## Testing

Run the test suite:
```bash
pytest tests/
```

## Automated Daily Discovery with GitHub Actions

You can set up automated daily issue discovery using GitHub Actions. The workflow will automatically discover new issues at 10 AM US Central Time daily.

**Quick Setup:**
1. Create a GitHub Personal Access Token with `public_repo` scope
2. Add it as a repository secret named `PAT_TOKEN`
3. The workflow will run automatically on the schedule defined in `.github/workflows/daily-discovery.yml`

For detailed setup instructions, see [GITHUB_ACTIONS_SETUP.md](GITHUB_ACTIONS_SETUP.md).

**Manual Trigger:**
You can also manually trigger the workflow from the Actions tab in your GitHub repository.

## Notes

- `dev_profile.json` and `issue_classifier.pkl` are excluded from git for privacy
- Database migrations are handled automatically on first run
- ML model works without profile data, but profile data significantly improves predictions
- Repository metadata is cached to reduce API calls

