# Contribution Matcher

An automated system that discovers GitHub issues, extracts structured data, matches them to your developer skills, and recommends the best contribution opportunities using hybrid scoring (rules + ML).

## Quick Start

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for a quick start guide.

## Documentation

- **[README](docs/README.md)** - Full documentation and usage guide
- **[Quick Start Guide](docs/QUICKSTART.md)** - Get started in minutes
- **[GitHub Actions Setup](docs/GITHUB_ACTIONS_SETUP.md)** - Automated daily discovery setup

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Main entry point
python main.py discover --limit 100
python main.py score --top 10
python main.py create-profile --github your-username
```

## Project Structure

```
contribution_matcher/
├── contribution_matcher/     # Main package
│   ├── api/                  # GitHub API integration
│   ├── parsing/              # Issue parsing and data extraction
│   ├── scoring/              # Issue scoring and ML training
│   ├── database/             # Database operations
│   ├── profile/              # Developer profile management
│   ├── cli/                  # Command-line interface
│   └── config.py             # Configuration
├── tests/                    # Test suite
├── docs/                     # Documentation
├── main.py                   # Entry point
└── requirements.txt          # Dependencies
```

## Testing

```bash
pytest tests/
```

