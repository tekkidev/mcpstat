# Contributing to mcpstat

Thank you for your interest in contributing to mcpstat! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Submitting Changes](#submitting-changes)
- [Reporting Issues](#reporting-issues)

## Code of Conduct

Please read and follow our [Code of Conduct](https://github.com/tekkidev/mcpstat/blob/main/CODE_OF_CONDUCT.md).

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/mcpstat.git
   cd mcpstat
   ```
3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Linux/macOS
   # or: venv\Scripts\activate  # Windows
   pip install -e ".[dev]"
   ```

## Development Setup

### Running the Tests

```bash
# Run all tests with coverage (configured in pyproject.toml)
pytest

# Run specific test file
pytest tests/test_mcpstat.py

# Run without coverage
pytest tests/ --no-cov
```

### Type Checking

```bash
mypy mcpstat/
```

### Linting

```bash
# Ruff (primary linter)
ruff check .

# Ruff with auto-fix
ruff check . --fix
```

## Coding Standards

### Style Guide

- Follow PEP 8 for Python code
- Use snake_case for functions and variables
- Use CamelCase for class names
- Maximum line length: 127 characters

### Code Quality Tools

#### Pre-commit Hooks (Recommended)

Install pre-commit hooks to automatically check code quality before commits:

```bash
# Install pre-commit
pip install pre-commit

# Install the git hooks
pre-commit install

# Run all hooks manually (optional)
pre-commit run --all-files
```

The pre-commit configuration includes:
- **Ruff**: Fast Python linting and formatting
- **Mypy**: Static type checking
- **Bandit**: Security vulnerability scanning
- **Standard hooks**: Trailing whitespace, YAML/TOML/JSON validation

#### Manual Quality Checks

```bash
# Full check suite (before PR)
ruff check .
mypy mcpstat/
pytest tests/ -v

# Format code
ruff format .
```

### Documentation

- Add docstrings to all public methods and classes
- Follow Google-style docstrings
- Update README.md if adding user-facing features

### Type Hints

- Use type hints for function parameters and return values
- Use `TYPE_CHECKING` for import-only type hints

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.types import Tool
```

## Submitting Changes

### Commit Messages

Follow conventional commit format:

```
type(scope): short description

Longer description if needed.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

### Pull Request Process

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes with clear, descriptive commits
3. Ensure all checks pass:
   ```bash
   pytest tests/
   mypy mcpstat/
   ruff check .
   ```
4. Push to your fork and create a pull request

### Pull Request Checklist

- [ ] Tests pass locally
- [ ] Code follows style guidelines (ruff, mypy clean)
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] Commits are clean and well-described

## Reporting Issues

### Bug Reports

Include:
- mcpstat version (`pip show mcpstat`)
- Python version (`python --version`)
- Operating system
- Minimal reproducible example
- Expected vs actual behavior
- Error messages or logs

### Feature Requests

Include:
- Clear description of the feature
- Use case / motivation
- Possible implementation approach (optional)

## Questions?

- Open a [GitHub Discussion](https://github.com/tekkidev/mcpstat/discussions)
- Check existing [issues](https://github.com/tekkidev/mcpstat/issues)

---

Thank you for contributing to mcpstat! 🎉
