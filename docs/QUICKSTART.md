# Contribution Matcher - Quick Start Guide

## Initial Setup

1. **Install dependencies:**
```bash
cd contribution_matcher
pip install -r requirements.txt
```

2. **Set up environment variables:**
Create a `.env` file:
```
PAT_TOKEN=your_github_personal_access_token
```

3. **Initialize database:**
The database will be created automatically on first use.

## Basic Workflow

### 1. Create Your Developer Profile

**Option A: From GitHub**
```bash
python main.py create-profile --github your-username
```

**Option B: From Resume**
```bash
python main.py create-profile --resume path/to/resume.pdf
```

**Option C: Manual**
```bash
python main.py create-profile --manual
```

### 2. Discover Issues

```bash
# Search for issues with default labels
python main.py discover --limit 100

# Search for Python issues
python main.py discover --language python --limit 50

# Search for issues in repos with 100+ stars
python main.py discover --stars 100 --limit 50
```

### 3. Score Issues

```bash
# Score all issues and show top 10
python main.py score --top 10

# Score with detailed breakdown
python main.py score --top 5 --verbose

# Score specific issue
python main.py score --issue-id 123
```

### 4. List Issues

```bash
# List beginner issues
python main.py list --difficulty beginner --limit 20

# List Python issues
python main.py list --technology python --limit 10
```

### 5. Train ML Model (Optional)

```bash
# Export issues for labeling
python main.py label-export --output issues_to_label.csv --limit 250

# Edit CSV file: Add 'good' or 'bad' in the 'label' column

# Import labels
python main.py label-import --input issues_to_label.csv

# Check progress
python main.py label-status

# Train model (after 200+ labels)
python main.py train-model
```

## Example Session

```bash
# 1. Create profile from GitHub
python main.py create-profile --github your-username

# 2. Discover new issues
python main.py discover --language python --limit 100

# 3. View statistics
python main.py stats

# 4. Get top matches
python main.py score --top 10 --verbose

# 5. Export top matches
python main.py score --top 20 --format json > top_matches.json
```

## Troubleshooting

**"GITHUB_TOKEN must be set":**
- Create `.env` file with your GitHub token
- Token must have `public_repo` scope

**"No issues found":**
- Check your GitHub token is valid
- Try different search criteria (remove filters)
- Check rate limit status

**"Profile not found":**
- Run `create-profile` command first
- Check that `dev_profile.json` exists

**Import errors:**
- Make sure all dependencies are installed: `pip install -r requirements.txt`
- Check Python version (3.8+)

