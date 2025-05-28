# CONTRIBUTING.md

## Introduction

Thank you for contributing to this project.

> Automated versioning and release tagging are managed using a GitHub Actions workflow.
> You do not need to install or configure any Git hooks locally.

Version and release metadata are stored in `lib/info.yaml` and are automatically updated after pull request merges, using the commit message of the merge commit.

---

## Workflow Overview

- You propose changes on a feature branch and open a pull request (PR).
- To request a version bump or set a specific version/tag, include a version tag in the PR title.
- After merge (using "Squash and merge"), a GitHub Actions workflow (`.github/workflows/versioning.yml`) will:
  - Parse the PR title (which becomes the merge commit message)
  - Validate and apply the appropriate version change in `lib/info.yaml`
  - Commit the metadata update (as `github-actions[bot]`)
  - Create a matching Git tag (e.g. `v2.5.0`) on the main branch

---

## How to Request a Version Bump

Include a tag in your PR title. The workflow supports:

| Tag                | Action                                 | Example PR Title                      |
|--------------------|----------------------------------------|---------------------------------------|
| `[major]`          | Bump major version (X → X+1.0.0)       | `[major] Rewrite internals`           |
| `[minor]`          | Bump minor version (Y → Y+1)           | `[minor] Add option for format`       |
| `[patch]`          | Bump patch version (Z → Z+1)           | `[patch] Fix typos and style`         |
| `[bump]`           | Same as `[patch]`, for convenience     | `[bump] Update citation link`         |
| `[vX.Y.Z]`         | Set exact version (overrides bumps)    | `[v2.5.0] Release new version`        |
| No tag or `[no v]` | Skip versioning; update timestamp only | `Adjust spacing [no v]`               |

Multiple tags are allowed, but only the most significant one is used:
`[major] > [minor] > [patch]/[bump]`

Redundant tags will trigger a warning in the Actions log.

---

## What Happens Automatically

After your PR is merged (usually with "Squash and merge"):

- The workflow:
  - Extracts the tag from the merge commit message (usually the PR title)
  - Validates and applies the version bump, with checks to ensure:
    - No version downgrades
    - No duplicate versions (unless `[allow same version]` is present)
    - Warnings for large version jumps
  - Updates `lib/info.yaml` fields:
    - `version`
    - `releasedate-*`
    - `latest-commit-msg`
    - `latest-commit-date`
  - Creates and pushes a corresponding Git tag (e.g., `v2.5.0`).

---

## Example PR Titles

[minor] Add support for custom plugins
[bump] Update citation link for paper
[v2.5.0] Release 2.5.0 with new features
Fix typos in docs [patch]

Tip: If you do not want a version bump for your PR, use `[no v]` or omit tags.

---

## Checking Version Updates

After your PR is merged:
- The bot may create a new commit updating `lib/info.yaml` and the version tag.
- You can view the workflow and tag activity under the Actions tab and Tags tab on GitHub.
- The `latest-commit-msg` and `version` fields in `lib/info.yaml` will reflect your change.

---

## Notes

- You do not need to edit or stage `lib/info.yaml`. The workflow takes care of this.
- Always use "Squash and merge" to ensure your PR title becomes the merge commit message.
- If you need to repeat a version (very rare), include `[allow same version]` in your PR title.
- Accidental version downgrades are rejected by the workflow.
- If the bot doesn't update the version or tag as expected, check the Actions logs for details.

---

## Troubleshooting

- Workflow failed?
  - Check the Actions tab for error logs (for example: invalid version string, downgrade, duplicate version, etc.).
  - Fix PR title/tag and try again (e.g., by editing your PR title and re-merging/rebasing).
- Tag didn't appear?
  - Only specific tag patterns (`[vX.Y.Z]`, `[major]`, `[minor]`, `[patch]`, `[bump]`) will trigger a new tag.
- Need a silent/no-bump change?
  - Use `[no v]` in your PR title, or no tag (only dates/commit message will update).

---

## Thank You

We appreciate your contributions!
Automated versioning ensures clear project history and reproducibility for all users.

For help, open an issue or contact the maintainers.

---

## (If you're still running old hooks)

- Old instructions for Git hooks (now deprecated) are no longer needed; versioning is now fully automated by GitHub Actions.