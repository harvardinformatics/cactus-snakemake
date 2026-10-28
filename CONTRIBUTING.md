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

## Running tests

The tests in `tests/` are built on the two datasets tracked in the repository: `tests/evolverMammals/` (for `align`, `add-genome`, `replace-genome` and `add-outgroup`) and `tests/yeast-minigraph/` (for `minigraph`). Tests only read those files; everything they write goes to pytest's temporary directory, and test configs always set `overwrite_original_hal: False`.

`pytest` is not part of `envs/environment.yml`, so install it into the environment you test from (e.g. `mamba install -n cactus-snakemake pytest`) and run it from the repository root:

```bash
pytest tests/unit                       # tier 1
pytest tests/unit tests/pipeline        # tiers 1 and 2
CACTUS_SMK_RUN_E2E=1 pytest tests/integration   # tier 3 (opt-in, submits cluster jobs)

# tier 3 with automatic partition selection
CACTUS_SMK_RUN_E2E=1 CACTUS_SMK_E2E_ARGS="-e slurm -j 20 --slurm-partition-config <partition config>" pytest tests/integration --basetemp=<dir on shared storage>
```

Tier 3 submits cluster jobs that write into the test output directories, so give pytest a `--basetemp` on storage the compute nodes can see. pytest's default is under `/tmp`, which is local to each node. pytest empties the `--basetemp` directory at the start of each run, so use one that holds nothing else.

| Tier | Location | What it checks | Needs | Time |
| ---- | -------- | -------------- | ----- | ---- |
| 1 | `tests/unit/` | Tree and seqfile parsing, resources, bind paths, prep manifests and fingerprints, and the `cactus_snakemake` wrapper's argument handling, `init` and `version` | Python, pyyaml, requests | seconds |
| 2 | `tests/pipeline/` | Each pipeline's real prep step (in the container) and Snakemake dry-runs: prep outputs match the tracked files, job plans match the pre-v4 baselines, dry-runs change nothing, and changed configs are detected as stale | singularity, a local non-GPU Cactus image; the evolverMammals HAL for `add-genome`, `replace-genome` and `add-outgroup` | ~11 minutes |
| 3 | `tests/integration/` | Full runs of every pipeline, their outputs, and that a dry-run afterwards has nothing left to do | the above, plus cluster access | hours |

Tier 1 runs on every pull request into `main` (`.github/workflows/tests.yml`). Tiers 2 and 3 need singularity and a Cactus image, so run them on the cluster before merging changes to the Snakefiles or `lib/`. Tests that need something missing are skipped, with the reason shown by `pytest -rs`.

Tier 2's expected job counts were captured from the v3.5.0 pipelines. A change to a pipeline's job plan fails those tests on purpose; update the expected counts only if the change is intended.

Environment variables:

| Variable | Used by | Default |
| -------- | ------- | ------- |
| `CACTUS_SMK_TEST_IMAGE` | tiers 2, 3 | The newest non-GPU `cactus_v*.sif` in `tests/evolverMammals/` or `tests/yeast-minigraph/` (images are not tracked) |
| `CACTUS_SMK_TEST_HAL` | tier 2 | `tests/evolverMammals/evolverMammals-out/evolverMammals.hal`, from running `align` on the mammals dataset (not tracked) |
| `CACTUS_SMK_TEST_SNAKEMAKE` | tiers 2, 3 | The `snakemake` next to the Python running pytest. Point it at another environment's `snakemake` (e.g. one made by `cactus_snakemake setup`) to test that environment's Snakemake version. |
| `CACTUS_SMK_RUN_E2E` | tier 3 | Unset: tier 3 is skipped. Set to `1` to run it. |
| `CACTUS_SMK_E2E_ARGS` | tier 3 | `-e slurm -j 20` |

---

## Thank You

We appreciate your contributions!
Automated versioning ensures clear project history and reproducibility for all users.

For help, open an issue or contact the maintainers.

---

## (If you're still running old hooks)

- Old instructions for Git hooks (now deprecated) are no longer needed; versioning is now fully automated by GitHub Actions.