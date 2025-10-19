# Contributing to LinkedIn Gateway

Thank you for your interest in contributing to LinkedIn Gateway! This document provides guidelines and instructions for contributing to the project.

## 🎯 Ways to Contribute

- 🐛 **Report bugs** - Help us identify and fix issues
- ✨ **Suggest features** - Share ideas for improvements
- 📝 **Improve documentation** - Help others understand the project
- 💻 **Submit code** - Fix bugs or implement features
- 🧪 **Write tests** - Increase code coverage and reliability
- 🌍 **Translate** - Help make the project accessible worldwide

## 📋 Before You Start

1. **Check existing issues** - Someone might already be working on it
2. **Read the documentation** - Understand the project structure
3. **Search discussions** - Your question might already be answered
4. **Review the code of conduct** - Be respectful and constructive

## 🐛 Reporting Bugs

When reporting bugs, please include:

- **Clear title** - Describe the issue concisely
- **Steps to reproduce** - How can we see the bug?
- **Expected behavior** - What should happen?
- **Actual behavior** - What actually happens?
- **Environment details**:
  - OS (Windows, Linux, macOS)
  - Python version
  - Docker version (if applicable)
  - Browser version
  - Extension version
- **Logs/screenshots** - Any relevant error messages

### Bug Report Template

```markdown
**Description**
A clear description of the bug.

**To Reproduce**
1. Go to '...'
2. Click on '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g., Windows 11]
- Python: [e.g., 3.11.5]
- Docker: [e.g., 24.0.6]
- Browser: [e.g., Chrome 120]

**Logs**
```
Paste relevant logs here
```

**Screenshots**
If applicable, add screenshots.
```

## ✨ Suggesting Features

Feature requests should include:

- **Use case** - Why is this feature needed?
- **Proposed solution** - How should it work?
- **Alternatives considered** - What other approaches did you think about?
- **Additional context** - Any other relevant information

## 💻 Contributing Code

### Setting Up Development Environment

1. **Fork the repository**:
   ```bash
   # Click "Fork" on GitHub, then:
   git clone https://github.com/YOUR-USERNAME/linkedin-gateway.git
   cd linkedin-gateway
   git remote add upstream https://github.com/vcentea/linkedin-gateway.git
   ```

2. **Set up backend**:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/base.txt
   pip install -r requirements/dev.txt  # Development dependencies
   ```

3. **Set up database**:
   ```bash
   # Use Docker for quick setup (requires Docker & Docker Compose pre-installed)
   cd deployment
   ./scripts/install-core.sh
   
   # Or install PostgreSQL manually
   # Then run migrations:
   alembic upgrade head
   ```

4. **Set up Chrome extension**:
   ```bash
   cd chrome-extension
   npm install
   npm run build:dev
   ```

### Development Workflow

1. **Create a branch**:
   ```bash
   git checkout -b feature/your-feature-name
   # Or: git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**:
   - Write clean, readable code
   - Follow existing code style
   - Add comments for complex logic
   - Write tests for new features

3. **Test your changes**:
   ```bash
   # Backend tests
   cd backend
   pytest

   # Extension tests
   cd chrome-extension
   npm test

   # Manual testing
   # - Test the API endpoints
   # - Test the Chrome extension
   # - Verify database changes
   ```

4. **Commit your changes**:
   ```bash
   git add .
   git commit -m "feat: add awesome feature"
   ```

   **Commit Message Format**:
   - `feat: new feature`
   - `fix: bug fix`
   - `docs: documentation changes`
   - `style: code style changes`
   - `refactor: code refactoring`
   - `test: add or update tests`
   - `chore: maintenance tasks`

5. **Push and create PR**:
   ```bash
   git push origin feature/your-feature-name
   ```
   Then create a Pull Request on GitHub.

### Code Standards

#### Python (Backend)

- Follow **PEP 8** style guide
- Use **type hints** for function parameters and returns
- Maximum line length: **88 characters** (Black formatter)
- Use **docstrings** for functions and classes
- Write **meaningful variable names**
- Keep functions **small and focused**

Example:
```python
from typing import Optional

def get_user_profile(user_id: str, include_details: bool = False) -> Optional[dict]:
    """
    Fetch user profile from LinkedIn.
    
    Args:
        user_id: LinkedIn user identifier
        include_details: Whether to include extended details
        
    Returns:
        User profile dict or None if not found
    """
    # Implementation here
    pass
```

#### JavaScript (Extension)

- Follow **ESLint** configuration
- Use **const** and **let** (no var)
- Use **async/await** over promises
- Add **JSDoc comments** for complex functions
- Use **meaningful names**

Example:
```javascript
/**
 * Fetch LinkedIn profile data
 * @param {string} profileId - LinkedIn profile identifier
 * @returns {Promise<Object>} Profile data
 */
async function fetchProfile(profileId) {
  const response = await fetch(`/api/profiles/${profileId}`);
  return response.json();
}
```

#### General Guidelines

- **DRY**: Don't Repeat Yourself
- **KISS**: Keep It Simple, Stupid
- **YAGNI**: You Aren't Gonna Need It
- **Test your code** before submitting
- **Update documentation** when changing functionality
- **Handle errors gracefully**

### Pull Request Guidelines

#### Before Submitting

- ✅ Code follows project style guidelines
- ✅ Tests pass locally
- ✅ New code has tests
- ✅ Documentation is updated
- ✅ No merge conflicts
- ✅ Commit messages are clear

#### PR Description

Include:
- **What** - What changes does this PR make?
- **Why** - Why are these changes needed?
- **How** - How do the changes work?
- **Testing** - How did you test the changes?
- **Screenshots** - For UI changes
- **Breaking changes** - If any, list them
- **Related issues** - Link to related issues

#### PR Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## How Has This Been Tested?
Describe testing steps.

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-reviewed code
- [ ] Commented complex code
- [ ] Updated documentation
- [ ] No new warnings
- [ ] Added tests
- [ ] Tests pass locally

## Screenshots (if applicable)
Add screenshots here.
```

### Review Process

1. **Automated checks** run (linting, tests)
2. **Maintainer review** - Code review and feedback
3. **Address feedback** - Make requested changes
4. **Approval** - PR is approved
5. **Merge** - Changes are merged to main

## 🧪 Testing

### Running Tests

```bash
# Backend tests
cd backend
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_api.py

# Extension tests
cd chrome-extension
npm test
```

### Writing Tests

- Write tests for **new features**
- Write tests for **bug fixes**
- Test **edge cases**
- Test **error handling**
- Aim for **high coverage**

Example test:
```python
def test_get_profile_success(client, auth_headers):
    """Test successful profile retrieval"""
    response = client.get("/api/v1/profiles/me", headers=auth_headers)
    assert response.status_code == 200
    assert "firstName" in response.json()
    
def test_get_profile_unauthorized(client):
    """Test profile retrieval without authentication"""
    response = client.get("/api/v1/profiles/me")
    assert response.status_code == 401
```

## 📝 Documentation

### Types of Documentation

- **Code comments** - Explain why, not what
- **API docs** - Document endpoints and parameters
- **User guides** - Help users use the product
- **Developer docs** - Help developers contribute

### Documentation Standards

- Use **clear, simple language**
- Include **examples**
- Keep docs **up to date**
- Add **screenshots** for UI features
- **Link** to related docs

## 🌍 Translation

Help translate the project:

1. Check `docs/translations/` for existing translations
2. Copy English version
3. Translate while preserving formatting
4. Submit as PR with `docs: add [language] translation`

## 🎨 Design Guidelines

When contributing UI changes:

- Follow **existing design patterns**
- Ensure **accessibility** (WCAG 2.1 AA)
- Test on **multiple browsers**
- Test on **different screen sizes**
- Use **semantic HTML**
- Provide **loading states**
- Handle **error states**

## ❓ Questions?

- 💬 **Discussions**: Use GitHub Discussions for questions
- 🐛 **Issues**: Use Issues for bugs/features only
- 📧 **Email**: For security issues, contact maintainers directly

## 📜 Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of:
- Age
- Body size
- Disability
- Ethnicity
- Gender identity
- Experience level
- Nationality
- Personal appearance
- Race
- Religion
- Sexual identity and orientation

### Our Standards

**Positive behavior**:
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Accepting constructive criticism
- Focusing on what's best for the community
- Showing empathy

**Unacceptable behavior**:
- Trolling, insulting/derogatory comments
- Personal or political attacks
- Public or private harassment
- Publishing others' private information
- Other unethical or unprofessional conduct

### Enforcement

Violations may result in:
1. Warning
2. Temporary ban
3. Permanent ban

Report violations to project maintainers.

## 🙏 Thank You!

Thank you for contributing to LinkedIn Gateway! Your efforts help make this project better for everyone.

---

**Remember**: The best PRs are small, focused, and well-tested. Don't hesitate to ask questions!

Happy coding! 🚀

