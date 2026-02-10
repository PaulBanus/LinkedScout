# LinkedScout

## Stack

### Core
- Python 3.14
- mise (version manager)
- uv (package manager)

### Application
- httpx (async HTTP client)
- pydantic (data validation)
- pydantic-settings (settings management)
- beartype (runtime type checking)
- selectolax (HTML parsing)
- PyYAML (YAML parsing)
- typer (CLI framework)
- rich (terminal formatting)

### Development
- pytest (testing framework)
- pytest-asyncio (async testing)
- pytest-cov (coverage reporting)
- respx (HTTP mocking for tests)
- ruff (linter and formatter)
- mypy (static type checker)
- types-pyyaml (type stubs)
- pre-commit (git hooks)

## Commands

### Search
- `uv run linkedscout search --keywords "..." --location "..."` - Search jobs
- Additional flags: `--remote`, `--hybrid`, `--on-site`, `--full-time`, `--contract`, `--time`, `--max`, `--output`

### Alerts
- `uv run linkedscout alerts list` - List saved alerts
- `uv run linkedscout alerts create NAME --keywords "..."` - Create alert
- `uv run linkedscout alerts run --all` - Run all alerts
- `uv run linkedscout alerts run --name NAME` - Run specific alert
- `uv run linkedscout alerts enable NAME` - Enable alert
- `uv run linkedscout alerts disable NAME` - Disable alert
- `uv run linkedscout alerts delete NAME` - Delete alert
- `uv run linkedscout alerts migrate --from alerts/ --to alerts.yaml` - Migrate from old format (one-time)

### Development

**Setup**
- `uv sync` - Install all dependencies
- `uv run pre-commit install` - Install pre-commit hooks

**Testing (pytest + pytest-asyncio + pytest-cov + respx)**
- `uv run pytest` - Run all tests
- `uv run pytest -v` - Verbose output (show test names)
- `uv run pytest --cov` - Run with coverage report
- `uv run pytest --cov --cov-report=html` - Generate HTML coverage report
- `uv run pytest tests/test_cli.py` - Run specific test file
- `uv run pytest -k "test_search"` - Run tests matching pattern
- `uv run pytest --asyncio-mode=auto -v` - Debug async issues

**Linting & Formatting (ruff)**
- `uvx ruff check src/` - Check for linting issues
- `uvx ruff check src/ --fix` - Auto-fix linting issues
- `uvx ruff format src/` - Format code
- `uvx ruff format src/ --check` - Check formatting without changes

**Type Checking (mypy)**
- `uv run mypy src/` - Type check all source code
- `uv run mypy src/ --verbose` - Verbose type checking
- `uv run mypy src/linkedscout/cli.py` - Type check specific file

**Pre-commit Hooks**
- `uv run pre-commit run` - Run hooks on staged files
- `uv run pre-commit run --all-files` - Run hooks on all files
- `uv run pre-commit autoupdate` - Update hook versions

## Project Structure
- `src/linkedscout/` - Main package (library)
- `src/linkedscout/models/` - Pydantic models
- `src/linkedscout/scraper/` - LinkedIn scraping logic
- `src/linkedscout/services/` - Business logic
- `src/linkedscout/storage/` - JSON/SQLite storage
- `src/linkedscout/utils/` - Utilities (rate limiter, etc.)
- `src/linkedscout/cli.py` - CLI entry point
- `alerts.yaml` - Alert definitions (all alerts in single file)
- `tests/` - Test suite
- `.pre-commit-config.yaml` - Pre-commit hooks configuration

## Code Style
- PEP 8 naming conventions
- Type hints required (validated by mypy and beartype)
- Docstrings in Google format
- Async/await for HTTP operations
- Line length: 88 characters (ruff formatter)

## Testing Strategy
- **Unit tests**: Test individual components in isolation
- **Async testing**: Use pytest-asyncio for async functions (asyncio_mode: auto)
- **HTTP mocking**: Use respx to mock httpx requests (no real network calls)
- **Coverage**: Aim for high coverage, use `pytest --cov` to verify
- **Test files**: `test_cli.py`, `test_models.py`, `test_parser_edge_cases.py`, `test_rate_limiter.py`

## Tool Configuration

### pytest (pyproject.toml)
- Test directory: `tests/`
- Asyncio mode: `auto` (automatic async fixture detection)
- Coverage source: `src/linkedscout`
- Branch coverage: enabled

### ruff (pyproject.toml)
- Line length: 88
- Target: Python 3.14
- Enabled rules: pycodestyle, pyflakes, isort, flake8-bugbear, pyupgrade, and more
- Import sorting: first-party package is `linkedscout`

### mypy (pyproject.toml)
- Strict mode: enabled
- Disallow untyped definitions
- Pydantic plugin: enabled
- Ignore missing imports: `selectolax` (no type stubs available)

### pre-commit (.pre-commit-config.yaml)
- Hooks: ruff (lint & format), mypy, YAML validation, trailing whitespace, end-of-file fixes
