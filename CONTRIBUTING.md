# Contributing to OmniRAG

Thank you for your interest in contributing!

## Getting Started

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest`
5. Run linter: `ruff check . && ruff format .`
6. Commit and open a Pull Request

## Code Style

- Python: PEP 8, enforced via `ruff`
- TypeScript: strict mode, Prettier
- Commit messages: Conventional Commits

## Adding New Ingestion Types

To add a new file type ingester:
1. Create `backend/ingestion/my_type_ingester.py`
2. Implement the `BaseIngester` interface
3. Register in `backend/main.py`
4. Add tests in `backend/tests/`

## Reporting Issues

Use GitHub Issues with logs and sample files (redact any sensitive data).
