## Description
<!-- Provide a brief description of the changes in this PR -->

## Related Issue
<!-- Link to the Linear/GitHub issue this PR addresses -->
- Linear Issue: AUR-XXX
- Link: 

## Type of Change
<!-- Mark the relevant option with an "x" -->
- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] ♻️ Code refactoring
- [ ] 🎨 Style/formatting changes
- [ ] ⚡ Performance improvements
- [ ] ✅ Test additions or updates

## Changes Made
<!-- List the main changes made in this PR -->
- 
- 
- 

## Testing
<!-- Describe the tests you ran to verify your changes -->
- [ ] Unit tests pass locally
- [ ] Integration tests pass locally
- [ ] Manual testing completed
- [ ] New tests added for new functionality
- [ ] Existing tests updated as needed

### Test Coverage
- Current coverage: __%
- Coverage after changes: __%

## Code Quality Checklist

### Functionality
- [ ] Code accomplishes the intended goal
- [ ] Edge cases are handled appropriately
- [ ] Error handling is comprehensive
- [ ] No obvious bugs or logic errors

### Code Standards
- [ ] Follows project naming conventions (snake_case for Python, camelCase for JS/TS)
- [ ] No code duplication (DRY principle)
- [ ] Functions are focused and single-purpose
- [ ] Complex logic is well-commented
- [ ] No commented-out code or debug statements

### Python Specific
- [ ] Type hints are used for all function signatures
- [ ] Docstrings follow Google style format
- [ ] Imports are properly organized (stdlib → third-party → local)
- [ ] No unused imports or variables
- [ ] Async/sync patterns used appropriately

### JavaScript/TypeScript Specific
- [ ] TypeScript types are properly defined (no `any` types)
- [ ] React hooks follow rules of hooks
- [ ] Component props are properly typed
- [ ] No console.log statements (except warnings/errors)

### Performance
- [ ] No unnecessary database queries (N+1 queries avoided)
- [ ] Efficient algorithms used where applicable
- [ ] Proper use of caching where appropriate
- [ ] No memory leaks or circular dependencies
- [ ] Database queries are optimized with proper indexes

### Security
- [ ] Input validation is comprehensive
- [ ] No SQL injection vulnerabilities
- [ ] Sensitive data is not logged or exposed
- [ ] Authentication/authorization checks are in place
- [ ] CORS settings are appropriate
- [ ] No hardcoded secrets or credentials

### Testing
- [ ] Adequate test coverage (≥80% for new code)
- [ ] Tests are meaningful and test actual functionality
- [ ] Edge cases and error conditions are tested
- [ ] Mocks are used appropriately
- [ ] Test data is properly isolated

### Documentation
- [ ] Functions have appropriate docstrings/JSDoc comments
- [ ] Complex business logic is explained
- [ ] API changes are documented
- [ ] README updated if necessary
- [ ] CHANGELOG updated (if applicable)

### Database
- [ ] Migrations are reversible
- [ ] Database schema changes are backward compatible
- [ ] Indexes are added for frequently queried columns
- [ ] Foreign key constraints are properly defined

## Pre-Commit Checks
<!-- These should pass automatically via pre-commit hooks -->
- [ ] `black` formatting (Python)
- [ ] `ruff` linting (Python)
- [ ] `isort` import sorting (Python)
- [ ] `mypy` type checking (Python)
- [ ] `prettier` formatting (JS/TS)
- [ ] `eslint` linting (JS/TS)
- [ ] No large files added
- [ ] No merge conflicts
- [ ] No private keys or secrets

## Screenshots/Videos
<!-- If applicable, add screenshots or videos to demonstrate the changes -->

## Deployment Notes
<!-- Any special considerations for deployment -->
- [ ] Database migrations required
- [ ] Environment variables added/changed
- [ ] Dependencies added/updated
- [ ] Breaking changes that require coordination

## Post-Deployment Verification
<!-- Steps to verify the deployment was successful -->
- [ ] Feature flags configured (if applicable)
- [ ] Monitoring/alerts configured
- [ ] Performance metrics baseline established

## Additional Notes
<!-- Any additional information that reviewers should know -->

---

## Reviewer Checklist
<!-- For code reviewers to check -->
- [ ] Code changes reviewed line by line
- [ ] Business logic is correct
- [ ] No security vulnerabilities identified
- [ ] Performance implications considered
- [ ] Tests are adequate and passing
- [ ] Documentation is clear and complete