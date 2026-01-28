# Contributing to VGC MCP Server

Thank you for your interest in contributing to the VGC MCP Server! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Reporting Bugs](#reporting-bugs)
- [Suggesting Features](#suggesting-features)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please:

- Be respectful and considerate in your interactions
- Welcome newcomers and help them get started
- Focus on constructive feedback
- Assume good intentions
- Respect differing viewpoints and experiences

## How Can I Contribute?

### Types of Contributions

We welcome all types of contributions:

1. **Bug Reports** - Found a bug? Let us know!
2. **Feature Requests** - Have an idea? Share it!
3. **Code Contributions** - Fix bugs, add features, improve performance
4. **Documentation** - Improve guides, add examples, fix typos
5. **Testing** - Write tests, improve coverage, test edge cases
6. **Community** - Help others in discussions, answer questions

### First Time Contributors

Looking to contribute for the first time? Look for issues tagged with:
- `good first issue` - Easy issues for newcomers
- `help wanted` - Issues where we need help
- `documentation` - Documentation improvements

## Development Setup

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed development setup instructions.

**Quick Start:**

```bash
# Clone the repository
git clone https://github.com/MSS23/vgc-mcp.git
cd vgc-mcp

# Install in development mode
pip install -e ".[dev]"

# Run tests to verify setup
python -m pytest tests/ -v
```

## Development Workflow

### 1. Fork and Clone

Fork the repository and clone your fork:

```bash
git clone https://github.com/YOUR_USERNAME/vgc-mcp.git
cd vgc-mcp
git remote add upstream https://github.com/MSS23/vgc-mcp.git
```

### 2. Create a Branch

Create a descriptive branch for your changes:

```bash
git checkout -b feature/add-new-tool
# or
git checkout -b fix/damage-calculation-bug
```

**Branch Naming:**
- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation changes
- `test/description` - Test additions/improvements
- `refactor/description` - Code refactoring

### 3. Make Changes

Make your changes following our code style guidelines (see below).

### 4. Test Your Changes

Run tests before committing:

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_damage.py -v

# Run with coverage
python -m pytest tests/ --cov=vgc_mcp
```

### 5. Commit Your Changes

Write clear, descriptive commit messages:

```bash
git add .
git commit -m "Add support for new Gen 9 ability: Opportunist

- Implement ability logic in calc/abilities.py
- Add tests in tests/test_abilities.py
- Update ability reference in docs
"
```

**Commit Message Guidelines:**
- First line: Brief summary (50 chars or less)
- Blank line
- Detailed description (wrap at 72 chars)
- Reference issues: "Fixes #123" or "Relates to #456"

### 6. Push and Create Pull Request

```bash
git push origin feature/add-new-tool
```

Then create a pull request on GitHub.

## Code Style Guidelines

We use automated tools to enforce code style:

### Python Code Style

- **Formatter**: Ruff (`ruff format`)
- **Linter**: Ruff (`ruff check`)
- **Type Checker**: MyPy (`mypy`)

**Run before committing:**

```bash
# Format code
ruff format src/

# Check for issues
ruff check src/

# Type checking
mypy src/vgc_mcp
```

### Style Conventions

- **Line Length**: 88 characters (Black default)
- **Imports**: Sorted with isort (integrated in ruff)
- **Type Hints**: Required for all function signatures
- **Docstrings**: Google style for public functions

**Example:**

```python
from typing import Optional

def calculate_damage(
    attacker_stat: int,
    defender_stat: int,
    move_power: int,
    modifier: float = 1.0,
) -> int:
    """Calculate damage using the Gen 9 damage formula.

    Args:
        attacker_stat: Attacker's relevant stat (Attack or Special Attack)
        defender_stat: Defender's relevant stat (Defense or Special Defense)
        move_power: Base power of the move
        modifier: Combined damage modifier (default: 1.0)

    Returns:
        Calculated damage value
    """
    base_damage = ((2 * 50 / 5 + 2) * move_power * attacker_stat / defender_stat / 50 + 2)
    return int(base_damage * modifier)
```

## Testing Requirements

### Writing Tests

- All new features must include tests
- Bug fixes should include regression tests
- Aim for 80%+ code coverage

### Test Structure

```python
# tests/test_new_feature.py
import pytest
from vgc_mcp_core.calc.damage import calculate_damage

class TestNewFeature:
    """Test suite for new feature."""

    def test_basic_case(self):
        """Test basic functionality."""
        result = calculate_damage(100, 100, 80)
        assert result > 0

    def test_edge_case(self):
        """Test edge case with zero defense."""
        # Edge cases should be handled gracefully
        ...
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test
python -m pytest tests/test_damage.py::TestDamageCalculation::test_stab -v

# Run with coverage
python -m pytest tests/ --cov=vgc_mcp --cov-report=html
```

## Pull Request Process

### Before Submitting

- [ ] Code follows style guidelines (ruff, mypy)
- [ ] Tests pass locally
- [ ] New code has tests
- [ ] Documentation updated (if needed)
- [ ] CHANGELOG.md updated (for significant changes)
- [ ] Branch is up-to-date with main

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Refactoring

## Changes Made
- Change 1
- Change 2

## Testing
- [ ] Added tests for new functionality
- [ ] All tests pass locally

## Checklist
- [ ] Code follows project style
- [ ] Documentation updated
- [ ] CHANGELOG.md updated (if applicable)

Fixes #123 (if applicable)
```

### Review Process

1. A maintainer will review your PR
2. Address any requested changes
3. Once approved, a maintainer will merge your PR
4. Your contribution will be included in the next release!

### After Your PR is Merged

- Update your local main branch
- Delete your feature branch
- Celebrate! 🎉

## Reporting Bugs

### Before Reporting

- Check if the bug is already reported in [Issues](https://github.com/MSS23/vgc-mcp/issues)
- Try to reproduce the bug with the latest version
- Gather relevant information (logs, steps to reproduce)

### Bug Report Template

```markdown
**Describe the Bug**
Clear description of what the bug is

**To Reproduce**
1. Use this Pokemon: '...'
2. Call this tool: '...'
3. See error

**Expected Behavior**
What you expected to happen

**Actual Behavior**
What actually happened

**Environment**
- OS: [e.g., Windows 11]
- Python Version: [e.g., 3.11.5]
- VGC MCP Version: [e.g., 0.1.0]

**Additional Context**
Any other information (screenshots, logs, etc.)
```

## Suggesting Features

We love feature suggestions! Please include:

1. **Use Case**: Why is this feature needed?
2. **Proposed Solution**: How should it work?
3. **Alternatives**: Other ways to solve the problem?
4. **Additional Context**: Examples, mockups, etc.

### Feature Request Template

```markdown
**Feature Description**
Clear description of the feature

**Use Case**
Why would this be useful?

**Proposed Solution**
How should this feature work?

**Alternatives**
Other ways to achieve this?

**Additional Context**
Examples, mockups, related features
```

## Development Resources

- **DEVELOPMENT.md** - Detailed development guide
- **TECHNICAL_GUIDE.md** - MCP architecture and internals
- **API_REFERENCE.md** - Complete tool reference
- **CLAUDE.md** - Claude Code integration guidelines

## Questions?

- Open a [Discussion](https://github.com/MSS23/vgc-mcp/discussions)
- Ask in an existing issue
- Contact maintainers

## Recognition

Contributors will be:
- Listed in CHANGELOG.md for their contributions
- Credited in release notes
- Part of the VGC MCP community!

Thank you for contributing! 🙏
