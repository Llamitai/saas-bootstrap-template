---
description: Update a pull request description with the project sections
---

# Update PR Description

## Task

Update the specified pull request's description. The repository has no PR template file, so use the sections below.

Use these sections:

- Issue (with "resolve:" field)
- Why is this change needed?
- What would you like reviewers to focus on?
- Testing Verification
- What was done (with pr_agent:summary placeholder)
- Detailed Changes (with pr_agent:walkthrough placeholder)
- Additional Notes

### Steps

1. Check the PR number provided in the arguments
2. Read the current PR description using `gh pr view`
3. Reformat the content into those sections; Testing Verification lists commands, results and unverified behavior
4. Keep existing pr_agent placeholders (pr_agent:summary, pr_agent:walkthrough) intact if present
5. Update the PR using `gh pr edit`

### Arguments

$ARGUMENTS
