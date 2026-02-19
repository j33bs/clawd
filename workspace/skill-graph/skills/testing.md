---
name: testing
description: Test-driven development, unit tests, integration tests, and test patterns
tags: [development, quality, testing]
links: [code-review, documentation, debugging]
---

# Testing

## Types of Tests

### Unit Tests
- Test individual functions/methods
- Fast, isolated, deterministic
- Mock external dependencies

### Integration Tests
- Test interactions between components
- Slower, may use test databases
- Verify data flow

### End-to-End Tests
- Test full user flows
- Slowest, most expensive
- Catch real-world issues

## Test-Driven Development (TDD)

1. **Red** - Write failing test first
2. **Green** - Make test pass with minimal code
3. **Refactor** - Improve code while keeping tests green

See [[code-review]] for reviewing test quality.

## Good Tests Are

- **Fast** - Run in milliseconds
- **Isolated** - Don't depend on each other
- **Repeatable** - Same results every time
- **Self-Validating** - Clear pass/fail
- **Timely** - Written close to production code

## Related

- [[code-review]] - Reviewing test quality
- [[debugging]] - When tests fail
- [[documentation]] - Test documentation
