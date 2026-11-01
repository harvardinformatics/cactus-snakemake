#!/bin/bash
#############################################################################
# Runs the tier-3 (end-to-end) tests as a SLURM job: every pipeline is prepped,
# run in full on the tracked test datasets, and checked (see tests/integration/).
# This job only runs pytest and the head Snakemake process; Snakemake submits
# the Cactus jobs as their own SLURM jobs.
#
# Submit from the repository root:
#   sbatch utils/run_e2e.sbatch
#
# The settings below can be overridden from the environment, e.g.
#   E2E_JOBS=40 sbatch utils/run_e2e.sbatch
#
# Each run writes to its own new directory, $E2E_ROOT/run-<SLURM job ID>, and
# nothing there is deleted afterwards. Snakemake's logs for each pipeline are in
# <that directory>/<test>/.snakemake/log/ while the run is going.
#############################################################################

#SBATCH --job-name=cactus-smk-e2e
#SBATCH --partition=shared
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=2-00:00:00
#SBATCH --output=cactus-smk-e2e-%j.out
# The Cactus jobs take about 3-4 hours in total when the queue is quick; the long
# time limit covers queue waits, which have added hours before.

set -euo pipefail

#############################################################################
# Settings

PYTEST_ENV="${PYTEST_ENV:-cactus-smk9}"
# Conda environment with pytest installed

SMK_ENV="${SMK_ENV:-cactus-tests}"
# Conda environment whose Snakemake is tested, e.g. one made by "cactus_snakemake setup"

PARTITION_CONFIG="${PARTITION_CONFIG:-/n/holylfs05/LABS/informatics/Everyone/internal-share/cannon-snakemake-cfg/cannon-snakemake.yml}"
# The test configs leave partitions blank, so the SLURM executor picks them from this file

E2E_ROOT="${E2E_ROOT:-/n/holylfs05/LABS/informatics/Users/gthomas/tmp/cactus-smk-e2e}"
# Where run directories are made. Must be on storage the compute nodes can see.

E2E_JOBS="${E2E_JOBS:-20}"
# Snakemake's -j: how many jobs it keeps submitted at once

#############################################################################
# Checks before anything runs

REPO="${SLURM_SUBMIT_DIR:?submit this script with sbatch}"
if [[ ! -f "$REPO/pytest.ini" || ! -f "$REPO/cactus.smk" ]]; then
    echo "error: submit from the cactus-snakemake repository root (this was submitted from $REPO)" >&2
    exit 1
fi

for cmd in conda singularity sbatch sacct; do
    if ! command -v "$cmd" >/dev/null; then
        echo "error: $cmd is not on PATH in this job" >&2
        exit 1
    fi
done

if [[ ! -f "$PARTITION_CONFIG" ]]; then
    echo "error: partition config not found: $PARTITION_CONFIG" >&2
    exit 1
fi

SMK_PREFIX="$(conda run -n "$SMK_ENV" python -c 'import sys; print(sys.prefix)')"
SNAKEMAKE="$SMK_PREFIX/bin/snakemake"
if [[ ! -x "$SNAKEMAKE" ]]; then
    echo "error: no snakemake in the $SMK_ENV environment ($SNAKEMAKE)" >&2
    exit 1
fi

BASETEMP="$E2E_ROOT/run-$SLURM_JOB_ID"
# pytest empties its --basetemp directory before it starts, so only a directory that
# doesn't exist yet is ever given to it
if [[ -e "$BASETEMP" ]]; then
    echo "error: $BASETEMP already exists" >&2
    exit 1
fi
mkdir -p "$E2E_ROOT"

echo "Repository:       $REPO ($(git -C "$REPO" rev-parse --abbrev-ref HEAD) @ $(git -C "$REPO" rev-parse --short HEAD))"
echo "Snakemake:        $SNAKEMAKE ($("$SNAKEMAKE" --version))"
echo "Partition config: $PARTITION_CONFIG"
echo "Run directory:    $BASETEMP"
echo "Test image:       ${CACTUS_SMK_TEST_IMAGE:-newest non-GPU cactus_v*.sif in tests/evolverMammals or tests/yeast-minigraph}"
echo "Started:          $(date)"
echo

#############################################################################
# Run

# sbatch passes the submitting environment on to the jobs it starts, and that includes
# this job's own SLURM_* settings. Clear them so the jobs Snakemake submits get only
# the resources they ask for, as they would if Snakemake were run from a login node.
while read -r var; do
    unset "$var"
done < <(compgen -e | grep -E '^(SLURM|SRUN)_')

export CACTUS_SMK_RUN_E2E=1
export CACTUS_SMK_TEST_SNAKEMAKE="$SNAKEMAKE"
export CACTUS_SMK_E2E_ARGS="-e slurm -j $E2E_JOBS --slurm-partition-config $PARTITION_CONFIG"
export PYTHONUNBUFFERED=1

cd "$REPO"

set +e
conda run -n "$PYTEST_ENV" --no-capture-output \
    pytest tests/integration -v -ra --durations=0 --basetemp="$BASETEMP"
rc=$?
set -e

echo
echo "Finished:         $(date)"
echo "pytest exit code: $rc"
exit "$rc"
