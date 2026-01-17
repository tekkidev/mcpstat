# Contributing to mcpstat

Thank you for your interest in contributing to mcpstat! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md).

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
   source venv/bin/activate
   pip install -e ".[dev]"
   ```

## Development Workflow

### Running Tests

```bash
pytest tests/ --cov=mcpstat --cov-report=term-missing
```

### Type Checking

```bash
mypy mcpstat
```

### Linting

```bash
ruff check mcpstat
```

### Pre-commit Checks

Before submitting a PR, ensure all checks pass:

```bash
pytest tests/
mypy mcpstat
ruff check mcpstat
```

## Submitting Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Make your changes with clear, descriptive commits
3. Ensure all tests pass and code is properly formatted
4. Push to your fork and create a pull request

## Pull Request Guidelines

- Provide a clear description of the changes
- Reference any related issues
- Include tests for new functionality
- Update documentation as needed
- Keep changes focused and atomic

## Reporting Issues

When reporting issues, please include:

- mcpstat version (`pip show mcpstat`)
- Python version (`python --version`)
- Operating system
- Minimal reproducible example
- Expected vs actual behavior

## Questions?

Feel free to open a [discussion](https://github.com/tekkidev/mcpstat/discussions) or [issue](https://github.com/tekkidev/mcpstat/issues) if you have questions.
