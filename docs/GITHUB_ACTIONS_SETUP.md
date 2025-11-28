# GitHub Actions Setup for Daily Issue Discovery

This guide explains how to set up automated daily issue discovery using GitHub Actions.

## Overview

The GitHub Actions workflow runs daily at 10 AM US Central Time to automatically discover new GitHub issues and store them in your database. This keeps your issue database up-to-date without manual intervention.

## Prerequisites

1. A GitHub repository (this project)
2. A GitHub Personal Access Token with appropriate permissions

## Step-by-Step Setup

### 1. Create GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Give it a descriptive name (e.g., "Contribution Matcher Daily Discovery")
4. Select the following scopes:
   - `public_repo` - To read public repositories and issues
   - `read:user` - To read user information (if creating profiles from GitHub)
5. Click "Generate token"
6. **Copy the token immediately** - you won't be able to see it again!

### 2. Add Token as Repository Secret

1. Go to your repository on GitHub
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `PAT_TOKEN`
5. Value: Paste your GitHub Personal Access Token
6. Click **Add secret**

### 3. Verify Workflow File

The workflow file is located at `.github/workflows/daily-discovery.yml`. It should:
- Run daily at 10 AM US Central Time (15:00 UTC)
- Install dependencies
- Run the discovery command
- Display statistics

### 4. Enable GitHub Actions

1. Go to your repository on GitHub
2. Click on **Actions** tab
3. If this is your first workflow, click **I understand my workflows, enable them**
4. The workflow will run automatically on the schedule

## Workflow Schedule

The workflow runs daily at **10 AM US Central Time**:
- **10 AM CDT** (Daylight Saving Time): 15:00 UTC
- **10 AM CST** (Standard Time): 16:00 UTC

The current schedule is set to 15:00 UTC (10 AM CDT). If you need to adjust for daylight saving time, edit `.github/workflows/daily-discovery.yml` and change the cron schedule:
- For CST: `'0 16 * * *'` (4 PM UTC)
- For CDT: `'0 15 * * *'` (3 PM UTC)

## Manual Triggering

You can manually trigger the workflow at any time:
1. Go to **Actions** tab in your repository
2. Select **Daily Issue Discovery** workflow
3. Click **Run workflow** button
4. Select the branch and click **Run workflow**

## What the Workflow Does

1. **Checkout code**: Gets the latest version of your repository
2. **Set up Python**: Installs Python 3.10
3. **Install dependencies**: Installs packages from `requirements.txt`
4. **Run discovery**: Executes `python contribution_matcher.py discover --limit 100`
5. **Display statistics**: Shows summary of discovered issues

## Database Persistence

**Current Implementation**: The workflow is configured to automatically commit the database to the repository after each discovery run. This means:
- The database persists across runs
- Each run builds upon the previous database
- You can pull the latest database locally with `git pull`
- The database file (`contribution_matcher.db`) is tracked in the repository

**How it works**:
1. The workflow checks out the latest code (including existing database)
2. Runs discovery to add new issues
3. Commits and pushes the updated database back to the repository
4. Uses `[skip ci]` in commit message to prevent infinite loops

**To get the latest database locally**:
```bash
git pull
```

**Note**: The database file is tracked in git (exception made in `.gitignore`). If you prefer not to track it, you can use one of the alternative options below.

### Alternative Options

If you don't want to commit the database to the repository, you have these options:

### Option 1: Use GitHub Artifacts
Store the database as an artifact and download it at the start of each run:
```yaml
- name: Download previous database
  uses: actions/download-artifact@v4
  with:
    name: issue-database
    path: .
  continue-on-error: true

- name: Upload database artifact
  uses: actions/upload-artifact@v4
  with:
    name: issue-database
    path: contribution_matcher.db
    retention-days: 30
```

### Option 2: External Storage
Store the database in cloud storage (S3, Google Cloud Storage, etc.) and sync it before/after runs.

## Troubleshooting

### Workflow Not Running

1. **Check Actions are enabled**: Go to Settings → Actions → General, ensure "Allow all actions and reusable workflows" is selected
2. **Check schedule**: Verify the cron schedule in the workflow file
3. **Check workflow file**: Ensure `.github/workflows/daily-discovery.yml` exists and is valid YAML

### Authentication Errors

1. **Token expired**: Generate a new token and update the `PAT_TOKEN` secret
2. **Insufficient permissions**: Ensure the token has `public_repo` scope
3. **Token not set**: Verify `PAT_TOKEN` secret exists in repository settings

### Rate Limiting

If you hit GitHub API rate limits:
- The workflow includes rate limiting handling
- Consider reducing the `--limit` parameter in the discovery command
- Add delays between API calls if needed

### Database Not Persisting

- By default, the database is recreated on each run
- See "Database Persistence" section above for solutions

## Monitoring

To monitor workflow runs:
1. Go to **Actions** tab in your repository
2. Click on **Daily Issue Discovery** to see run history
3. Click on a specific run to see detailed logs
4. Set up email notifications in repository settings if desired

## Customization

You can customize the workflow by editing `.github/workflows/daily-discovery.yml`:

- **Change schedule**: Modify the cron expression
- **Change discovery limit**: Update the `--limit` parameter
- **Add filters**: Add `--language`, `--stars`, or `--labels` parameters
- **Add notifications**: Add steps to send results via email, Slack, etc.

## Example Customizations

### Discover Python Issues Only
```yaml
- name: Run issue discovery
  run: |
    python main.py discover --language python --limit 50
```

### Discover High-Quality Repos
```yaml
- name: Run issue discovery
  run: |
    python main.py discover --stars 100 --limit 50
```

### Multiple Discovery Runs
```yaml
- name: Discover Python issues
  run: python main.py discover --language python --limit 50

- name: Discover JavaScript issues
  run: python main.py discover --language javascript --limit 50
```

## Security Best Practices

1. **Never commit tokens**: Always use GitHub Secrets
2. **Use minimal permissions**: Only grant necessary scopes to your token
3. **Rotate tokens regularly**: Update your token periodically
4. **Review workflow logs**: Check logs for any unexpected behavior
5. **Limit access**: Only give repository access to trusted collaborators

## Support

If you encounter issues:
1. Check the workflow logs in the Actions tab
2. Verify all secrets are set correctly
3. Test the discovery command locally first
4. Review the main README.md for general troubleshooting

