# Branch Protection Follow-up

## Purpose
Enforce deterministic CI gates on `main` and prevent direct push bypass.

References:
- [Managing a branch protection rule](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/managing-a-branch-protection-rule)
- [About protected branches](https://docs.github.com/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [REST API: branch protection](https://docs.github.com/en/rest/branches/branch-protection)

## GitHub UI Steps
1. Open repository settings: `Settings -> Branches`.
2. Under `Branch protection rules`, add or edit the rule for `main`.
3. Set branch name pattern to `main`.
4. Enable the settings below.
5. Save changes.

## Required Settings (main)
- `Require a pull request before merging`: blocks direct merges into `main`.
- `Require status checks to pass before merging`: ensures CI status gates are enforced.
- `Required status checks`:
  - `ci`
  - `node-test`
  - Note: Use exact names from the PR Checks tab; renaming jobs/workflows breaks bindings.
- `Require branches to be up to date before merging`: ensures checks run on the latest base.
- `Include administrators`: applies protections to admins and avoids privileged bypass.
- `Allow force pushes`: disabled.
- `Allow deletions`: disabled.
- `Restrict who can push to matching branches`: enable and keep scope minimal (or no direct push actors).

## Optional Hardening
- `Require pull request reviews before merging`: recommend at least 1 approval.
- `Require conversation resolution before merging`: blocks merge with unresolved review threads.
- Keep bypass lists empty except audited break-glass paths.

## Verification
- Open a PR and confirm merge is blocked until both `ci` and `node-test` are green.
- Attempt a direct push to `main` and confirm it is rejected after the rule is enabled.

## REST API Snippet (Illustrative)
```bash
curl -L -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/j33bs/clawd/branches/main/protection \
  -d '{
    "required_status_checks": {
      "strict": true,
      "checks": [
        { "context": "ci" },
        { "context": "node-test" }
      ]
    },
    "enforce_admins": true,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1
    },
    "allow_force_pushes": false,
    "allow_deletions": false
  }'
```
