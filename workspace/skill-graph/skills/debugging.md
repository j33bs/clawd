---
name: debugging
description: Systematic debugging techniques, tools, and strategies
tags: [development, troubleshooting, tools]
links: [testing, code-review, logging]
---

# Debugging

## The Method

1. **Reproduce** - Can you consistently trigger the bug?
2. **Isolate** - Minimize the reproduction case
3. **Hypothesize** - What's causing the issue?
4. **Test** - Verify your hypothesis
5. **Fix** - Implement the solution
6. **Verify** - Does the fix work?

## Tools

- **Logs** - Start here. See [[logging]]
- **Debuggers** - Step through code, inspect state
- **Tests** - Write tests to isolate. See [[testing]]
- **Profiling** - Find performance issues
- **Bisect** - Find the commit that broke it

## Common Techniques

### Rubber Ducking
Explain the problem out loud. You'll often solve it yourself.

### Divide and Conquer
Binary search through code/logs to find the problematic area.

### Change One Thing
Systematically isolate variables.

### Check the Basics
- Typos
- Environment variables
- Version mismatches
- Cached data

## Related Skills

- [[testing]] - Writing tests to reproduce bugs
- [[logging]] - Adding debug output
- [[code-review]] - Having another set of eyes
