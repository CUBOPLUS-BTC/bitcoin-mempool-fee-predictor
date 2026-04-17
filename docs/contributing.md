# 🤝 Contributing Guide

Thank you for your interest in contributing to the Bitcoin Mempool Fee Predictor!

---

## 🎯 Ways to Contribute

- **🐛 Bug Reports**: Report issues you encounter
- **💡 Feature Requests**: Suggest new features or improvements
- **📚 Documentation**: Improve docs, add examples
- **🔧 Code**: Fix bugs, add features, improve performance
- **🧪 Testing**: Write tests, improve coverage
- **🎨 UI/UX**: Improve the frontend interface

---

## 🚀 Getting Started

### 1. Fork the Repository

```bash
git clone https://github.com/YOUR_USERNAME/bitcoin-mempool-fee-predictor.git
cd bitcoin-mempool-fee-predictor
```

### 2. Set Up Development Environment

Follow the [Installation Guide](./installation.md).

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

---

## 📝 Development Guidelines

### Code Style

**Python**:
- Follow PEP 8
- Use type hints where possible
- Maximum line length: 100 characters
- Use `black` for formatting:
  ```bash
  black src/ api/ scripts/ tests/
  ```

**TypeScript/JavaScript**:
- Use ESLint configuration provided
- Follow existing code patterns
- Use TypeScript for new code

### Commit Messages

Use conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(api): add batch prediction endpoint

fix(inference): handle missing model files gracefully

docs(readme): update installation instructions

test(ensemble): add unit tests for confidence calculation
```

---

## 🔒 Security Considerations

When contributing code, ensure:

- ✅ No hardcoded secrets or API keys
- ✅ Input validation on all endpoints
- ✅ Proper error handling (don't expose internals)
- ✅ Updated dependencies (run `npm audit`, `pip-audit`)
- ✅ No SQL injection vulnerabilities
- ✅ XSS prevention in frontend code

### Security Checklist

Before submitting:
- [ ] No `print()` statements with sensitive data
- [ ] All user inputs validated
- [ ] Error messages are generic (in production)
- [ ] Dependencies have no known vulnerabilities
- [ ] CORS origins are properly configured
- [ ] Rate limiting is considered

---

## 🧪 Testing

### Running Tests

```bash
# Python tests
pytest tests/

# With coverage
pytest --cov=src --cov=api tests/

# Specific test file
pytest tests/test_inference.py
```

### Frontend Tests

```bash
cd frontend-react
npm test
```

### Linting

```bash
# Python
flake8 src/ api/ scripts/
black --check src/ api/ scripts/

# TypeScript
cd frontend-react
npm run lint
```

### Security Scan

```bash
# Python
bandit -r src/ api/ scripts/
pip-audit

# JavaScript
cd frontend-react
npm audit
```

---

## 📋 Pull Request Process

### 1. Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] Documentation updated (if needed)
- [ ] Security checklist completed
- [ ] Commit messages are clear

### 2. Submit PR

1. Push your branch to your fork
2. Create PR against `main` branch
3. Fill out the PR template:
   - What changes were made?
   - Why were they made?
   - How was it tested?
   - Any breaking changes?

### 3. PR Review

- Maintainers will review within 48 hours
- Address requested changes
- Keep discussions focused and professional

### 4. Merge

- Squash and merge when approved
- Delete your branch after merge

---

## 🐛 Reporting Bugs

### Before Reporting

- Search existing issues first
- Check if it's already fixed in `main`
- Try to reproduce consistently

### Bug Report Template

```markdown
**Description**
Clear description of the bug.

**Steps to Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Environment**
- OS: [e.g. Ubuntu 22.04]
- Python: [e.g. 3.11]
- Node: [e.g. 18.x]
- Browser: [if applicable]

**Logs/Screenshots**
If applicable, add logs or screenshots.

**Additional Context**
Any other relevant information.
```

---

## 💡 Feature Requests

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
Clear description of the problem.

**Describe the solution you'd like**
What should be implemented.

**Describe alternatives you've considered**
Other approaches you thought about.

**Additional context**
Any other information, mockups, etc.
```

---

## 📚 Documentation

### Updating Documentation

- Keep README.md concise (overview only)
- Add detailed docs to `docs/` folder
- Update API docs when endpoints change
- Add examples for new features

### Documentation Structure

```
docs/
├── README.md           # Documentation index
├── installation.md   # Setup guide
├── api-reference.md  # API docs
├── security.md       # Security guide
├── architecture.md   # System design
├── contributing.md   # This file
├── faq.md           # Common questions
└── changelog.md      # Version history
```

---

## 🏷️ Versioning

We follow [Semantic Versioning](https://semver.org/):

- `MAJOR.MINOR.PATCH`
- `MAJOR`: Breaking changes
- `MINOR`: New features (backward compatible)
- `PATCH`: Bug fixes

---

## 🙏 Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Accept constructive criticism
- Focus on what's best for the community

### Unacceptable Behavior

- Harassment or discrimination
- Trolling or insulting comments
- Personal attacks
- Publishing others' private information

---

## 📞 Getting Help

- **Discord**: [Join our community](https://discord.gg/...)
- **Issues**: [GitHub Issues](https://github.com/CUBOPLUS-BTC/bitcoin-mempool-fee-predictor/issues)
- **Email**: security issues only: security@example.com

---

## 🎉 Recognition

Contributors will be:
- Listed in README.md
- Mentioned in release notes
- Invited to contributor channels

Thank you for helping make Bitcoin fee prediction better!
