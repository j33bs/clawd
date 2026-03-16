# GitHub Skill

## Description
Manage GitHub issues, PRs, and repository operations.

## Triggers
- User mentions GitHub, issues, PRs, repos
- Commands: /gh, /github

## Actions
- list_issues: List open issues
- create_issue: Create new issue
- check_pr: Check PR status

## Error Handling
- Handle rate limits with backoff
- Handle auth errors gracefully
