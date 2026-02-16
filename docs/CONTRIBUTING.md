# Contributing to Bitcoin On-Chain Framework

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming environment

## How to Contribute

### Reporting Issues

1. Check if the issue already exists
2. Use the issue template
3. Provide detailed reproduction steps
4. Include system information (OS, Python version)

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest tests/`
5. Format code: `black src/ api/ scripts/`
6. Commit with clear messages
7. Push and create PR

### Coding Standards

- Follow PEP 8
- Use type hints
- Write docstrings for functions
- Add tests for new features
- Keep functions focused and small

### Testing

Run all tests before submitting:
```bash
pytest tests/ -v
```

### Documentation

- Update README.md for user-facing changes
- Update docstrings for code changes
- Add examples for new features

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/bitcoin-onchain-framework.git

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install development dependencies
pip install -r requirements.txt
pip install pytest black flake8

# Install pre-commit hooks (optional)
pre-commit install
```

## Questions?

Open an issue or reach out to the maintainers.
