# CONTRIBUTING.md

## Introduction

Thank you for contributing to this project.

This repository uses Git hooks and structured commit messages to manage versioning metadata in `lib/info.yaml`. When making commits, your messages help automate version bumps and update commit metadata. Please follow the guidelines below.

---

## Setup (one-time)

This project uses project-scoped Git hooks stored in `.githooks/`.

To enable them in your local clone:

1. Set Git to use the project hooks directory:

   ```bash
   git config core.hooksPath .githooks
   ```

2. Make sure all scripts are executable:

   ```bash
   chmod +x .githooks/*
   ```

---

## Commit Message Tags

Your commit message controls how the version is updated. Tag your commits with one of:

| Tag                | Action                                 | Example                                |
|--------------------|----------------------------------------|----------------------------------------|
| `[major]`          | Bump major version (X → X+1.0.0)       | `Rewrite internals [major]`            |
| `[minor]`          | Bump minor version (Y → Y+1)           | `Add option for format [minor]`        |
| `[patch]`          | Bump patch version (Z → Z+1)           | `Fix typos and style [patch]`          |
| `[bump]`           | Same as `[patch]`, for convenience     | `Update citation link [bump]`          |
| `[vX.Y.Z]`         | Set exact version (overrides bumps)    | `Release new version [v2.5.0]`         |
| No tag or `[no v]` | Skip versioning; update timestamp only | `Adjust spacing [no v]`                |

Multiple tags are allowed, but the most significant one will take effect:
`[major] > [minor] > [patch]/[bump]`

Redundant tags will trigger a warning.

---

## What Happens Automatically

When you commit:

- The `commit-msg` hook:
  - Parses your message
  - Validates version changes
  - Updates `lib/info.yaml` fields:
    - `version`
    - `releasedate-*`
    - `latest-commit-msg`
    - `latest-commit-date`
  - Rejects duplicate or downgraded versions
  - Prints warnings for large version jumps

- The `post-commit` hook:
  - If `info.yaml` was modified, creates a second commit:

    ```
    [info]
    ```

  - This ensures metadata is added reliably without interfering with your working commit

---

## Examples

```bash
git commit -m "Add option [minor]"
git commit -m "Adjust wording [bump]"
git commit -m "Release 3.0 final [v3.0.0]"
git commit -m "Improve formatting"
```

After each commit, you can check that the hooks ran and updated the info file with:

```bash
git log --oneline -n 2
git diff HEAD~1 lib/info.yaml
```

---

## Notes

- Be sure to `git add` the files you want in the commit before running `git commit`
- You do not need to stage or edit `lib/info.yaml` — it is handled automatically
- Do not squash or remove `[info]` commits — they are part of the versioning log

---

## Troubleshooting

- **Hook not firing?**
  - Check that `.githooks/commit-msg` and `.githooks/post-commit` are executable
  - Ensure `git config core.hooksPath` is set properly

- **Version not updating?**
  - Make sure you included a bump tag in your commit (like `[patch]` or `[v2.3.0]`)

- **Accidentally repeated a version?**
  - Add `[allow same version]` to override

---

## Thank You

We appreciate your contributions. Reliable versioning ensures reproducibility and clear project history.

Need help? Open an issue or contact the maintainers directly.