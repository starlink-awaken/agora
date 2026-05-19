# Contributing to Agora

Agora is the MCP service convergence hub for the Minerva ecosystem. Contributions are welcome.

## How to Contribute

### Reporting Bugs
Open an issue with: Agora version, Python version, steps to reproduce, expected vs actual output.

### Pull Requests
1. Fork and create a feature branch from `main`.
2. Install dev deps: `pip install -e ".[dev]"`.
3. Run linting: `ruff check src/agora/ --select F`.
4. Run tests: `pytest tests/ -q`.
5. Install pre-commit hooks: `pre-commit install`.
6. Use conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`).
7. Push and open a PR against `main`.

## Development Setup

```bash
git clone https://github.com/minerva/agora.git
cd agora
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Architecture

- `registry.py` — service registration with health check + circuit breaker
- `router.py` — tool→service routing with prefix + exact matching
- `cli.py` — 21 CLI commands
- `server/mcp.py` — 9 MCP tools

## Testing

```bash
pytest tests/ -q
pytest tests/ --cov=src/agora --cov-report=term-missing
```

## License

MIT. By contributing, you agree that your contributions will be licensed under MIT.
