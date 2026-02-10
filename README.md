# LinkedScout

Gather job listings from LinkedIn using multiple search criteria and obtain the list of all matching jobs in one place.

## Features

- Search LinkedIn jobs without authentication (public listings)
- Save search criteria as YAML alerts
- Filter by keywords, location, work model (remote/hybrid/on-site)
- Configurable time window (24h, 7 days, 30 days)
- Export to JSON with SQLite history
- Sort by publication date (most recent first)

## Stack

### Core Technologies
- [Python 3.14](https://www.python.org/) - Programming language
- [mise](https://mise.jdx.dev/) - Unified tool version manager (replaces pyenv, nvm, etc.)
- [uv](https://docs.astral.sh/uv/) - Ultra-fast Python package manager and resolver

### Application Libraries
- [httpx](https://www.python-httpx.org/) - Modern async HTTP client for API requests
- [Pydantic](https://docs.pydantic.dev/) - Data validation and settings management using Python type hints
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) - Settings management with environment variables and config files
- [beartype](https://beartype.readthedocs.io/) - Runtime type checker for validating function arguments and return values
- [selectolax](https://selectolax.readthedocs.io/) - Fast HTML/XML parser for web scraping
- [PyYAML](https://pyyaml.org/) - YAML parser for alert configuration files
- [Typer](https://typer.tiangolo.com/) - Modern CLI framework with type hints
- [Rich](https://rich.readthedocs.io/) - Beautiful terminal output and formatting

### Development Tools
- [pytest](https://docs.pytest.org/) - Testing framework with fixtures and plugins
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/) - pytest plugin for testing async code
- [pytest-cov](https://pytest-cov.readthedocs.io/) - Code coverage reporting for pytest
- [respx](https://lundberg.github.io/respx/) - Mock HTTP requests in tests (for httpx)
- [ruff](https://docs.astral.sh/ruff/) - Extremely fast Python linter and formatter (replaces flake8, black, isort)
- [mypy](https://mypy.readthedocs.io/) - Static type checker for Python
- [types-pyyaml](https://pypi.org/project/types-PyYAML/) - Type stubs for PyYAML (for mypy)
- [pre-commit](https://pre-commit.com/) - Git hooks framework for automated checks before commits

## Setup

```bash
mise trust
mise install
uv sync # uv sync --extra dev for dev dependencies
```

## Usage

### Search jobs

```bash
# Basic search
uv run linkedscout search --keywords "Python Developer" --location "Paris"

# With filters
uv run linkedscout search \
  --keywords "SRE" \
  --location "Europe" \
  --remote \
  --time 24h \
  --output jobs.json

# Additional options
uv run linkedscout search \
  --keywords "DevOps" \
  --location "London" \
  --on-site \
  --full-time \
  --max 50
```

### Manage alerts

```bash
# Create an alert
uv run linkedscout alerts create "python-remote" \
  --keywords "Python" \
  --location "France" \
  --remote

# List alerts
uv run linkedscout alerts list

# Run all alerts
uv run linkedscout alerts run --all

# Run all alerts with JSON output, will also update database
uv run linkedscout alerts run --all --output jobs.json

# Run specific alert
uv run linkedscout alerts run --name "python-remote"

# Enable/disable alerts
uv run linkedscout alerts enable "python-remote"
uv run linkedscout alerts disable "python-remote"

# Delete an alert
uv run linkedscout alerts delete "python-remote"
```

## Project Structure

```text
linkedscout/
├── src/linkedscout/      # Main package
│   ├── models/           # Pydantic data models
│   ├── scraper/          # LinkedIn scraping logic
│   ├── services/         # Business logic
│   ├── storage/          # JSON/SQLite storage
│   └── cli.py            # CLI entry point
├── alerts.yaml           # Alert definitions (all alerts in single file)
├── tests/                # Test suite
└── pyproject.toml        # Project configuration
```

## Alert Configuration

Alerts are stored in a single `alerts.yaml` file at the project root. The file contains a list of all alert definitions:

```yaml
alerts:
  - name: python-remote
    enabled: true
    criteria:
      keywords: Python Developer
      location: France
      time_filter: past_24h
      work_models:
        - remote
      job_types:
        - full_time
      max_results: 100

  - name: sre-europe
    enabled: true
    criteria:
      keywords: SRE
      location: Europe
      time_filter: past_week
      work_models:
        - remote
      job_types: []
      max_results: 100
```

You can create alerts via CLI (`linkedscout alerts create`) or by manually editing `alerts.yaml`.

### Available Values

| Field | Possible Values | Description |
|-------|-----------------|-------------|
| `time_filter` | `past_24h`, `past_week`, `past_month`, `any_time` | Time window for job postings |
| `work_models` | `on_site`, `remote`, `hybrid` | Work location preferences (can specify multiple) |
| `job_types` | `full_time`, `part_time`, `contract`, `internship`, `temporary`, `volunteer` | Employment types (can specify multiple) |
| `max_results` | `1` to `1000` | Maximum number of results to fetch (default: `100`) |

## Development

### Setup Development Environment

```bash
# Install all dependencies including dev dependencies
uv sync

# Install pre-commit hooks (runs checks before each commit)
uv run pre-commit install
```

### Testing with pytest

pytest is the testing framework used to ensure code quality and catch regressions. The project uses pytest-asyncio for testing async functions and respx for mocking HTTP requests.

```bash
# Run all tests
uv run pytest

# Run tests with verbose output (shows each test name)
uv run pytest -v

# Run tests with coverage report
uv run pytest --cov

# Run tests with coverage and generate HTML report
uv run pytest --cov --cov-report=html

# Run specific test file
uv run pytest tests/test_cli.py

# Run tests matching a pattern
uv run pytest -k "test_search"

# Run tests with asyncio debug mode (helpful for debugging async issues)
uv run pytest --asyncio-mode=auto -v
```

**Testing async code**: Tests for async functions are automatically detected and run using pytest-asyncio (configured in `pyproject.toml`).

**Mocking HTTP requests**: Use respx to mock httpx requests in tests without making real network calls.

### Code Quality with ruff

ruff is an extremely fast Python linter and formatter that replaces multiple tools (flake8, black, isort, etc.).

```bash
# Check code for linting issues
uvx ruff check src/

# Check and automatically fix issues
uvx ruff check src/ --fix

# Format code (similar to black)
uvx ruff format src/

# Check formatting without making changes
uvx ruff format src/ --check

# Run both linting and formatting
uvx ruff check src/ && uvx ruff format src/
```

### Type Checking with mypy

mypy performs static type checking to catch type-related bugs before runtime.

```bash
# Type check the source code
uv run mypy src/

# Type check with more verbose output
uv run mypy src/ --verbose

# Type check specific file
uv run mypy src/linkedscout/cli.py
```

### Pre-commit Hooks

pre-commit automatically runs checks before each git commit to maintain code quality.

```bash
# Install hooks (one-time setup)
uv run pre-commit install

# Manually run all hooks on staged files
uv run pre-commit run

# Run all hooks on all files
uv run pre-commit run --all-files

# Update hook versions
uv run pre-commit autoupdate
```

Configured hooks (see `.pre-commit-config.yaml`):
- ruff linting and formatting
- mypy type checking
- YAML validation
- Trailing whitespace removal
- End-of-file fixes

## Disclaimer

This tool accesses LinkedIn's public job listings for personal and educational use. While the data is publicly accessible, automated scraping may violate [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement). Use responsibly and at your own risk.

This project is not affiliated with or endorsed by LinkedIn.

## License

Apache-2.0 license
