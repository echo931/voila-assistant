# Contributing

## Development Setup

```bash
git clone https://github.com/echo931/voila-assistant.git
cd voila-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Code Style

- Python 3.11+
- Type hints for public functions
- Docstrings for modules and public APIs
- `ruff` for linting (coming soon)

## Project Structure

```
src/
├── cli.py           # Main CLI entry point
├── search.py        # Product search (Playwright)
├── cart.py          # Cart management (API + browser)
├── lists.py         # Shopping lists
├── local_cart.py    # Offline cart composition
├── needs.py         # Household needs tracking
├── preferences.py   # Product preferences
├── session.py       # Cookie/session management
├── client.py        # HTTP client utilities
├── models.py        # Data classes
└── exceptions.py    # Custom exceptions

tests/               # pytest test suite
skill/               # Clawdbot/OpenClaw skill definition
```

## Running Tests

```bash
python -m pytest tests/ -v
```

## How Voilà.ca Works

1. **Search**: Playwright loads search pages, extracts `window.__INITIAL_STATE__`
2. **Cart Read**: REST API `GET /api/cart/v1/carts/active`
3. **Cart Write**: Browser automation (API returns 403 for writes)
4. **Auth**: Cookies imported from browser (SSO blocks headless login)

## Pull Requests

1. Fork the repo
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit PR with clear description

## Reporting Issues

- Check existing issues first
- Include steps to reproduce
- Note your Python version and OS
