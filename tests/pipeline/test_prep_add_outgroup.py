#############################################################################
# Tier-2 tests for the add-outgroup pipeline's prep step and its make_input_files
# rule (cactus_add_outgroup.smk + lib/preplib.py), adding simGorilla as an outgroup
# to the evolverMammals HAL as configured in
# tests/evolverMammals/evolverMammals-add-outgroup-cfg.yaml. Prep only resolves the
# image here; make_input_files is run for real (it only writes two seqfiles, locally).
# Needs singularity, a local Cactus image and the evolverMammals HAL (see
# tests/helpers.py); skips otherwise. The HAL is only read.
#
# BASELINE_JOBS was captured from the pre-refactor pipeline (v3.5.0, which wrote
# the seqfiles on every parse) dry-running the same dataset.
#############################################################################

import os

import pytest

import lib.preplib as PREPLIB
from tests.helpers import (MAMMALS_DIR, dry_run, file_state, find_test_image, first_line, job_counts,
                           make_config, mammals_hal, run_prep, run_snakemake)

pytestmark = pytest.mark.prep

PIPELINE = "add-outgroup"

BASELINE_JOBS = {"align": 1, "all": 1, "blast": 1, "combine_hals": 1, "get_root_fasta": 1, "maf": 1, "preprocess": 1}

# The seqfiles written for this config by an earlier run
TRACKED_INPUT_FILES = {
    "add-outgroup-pre.txt": os.path.join(MAMMALS_DIR, "evolverMammals-add-out", "add-outgroup-pre.txt"),
    "add-outgroup-post.txt": os.path.join(MAMMALS_DIR, "evolverMammals-add-out", "add-outgroup-post.txt"),
}


def make_input_files(config_path, cwd):
    # Runs only the local make_input_files rule. -e slurm is needed for the tracked config's blank
    # partitions (see dry_run in tests/helpers.py); nothing is submitted.
    return run_snakemake(PIPELINE, config_path, cwd, ["-e", "slurm", "-j", "1", "--until", "make_input_files"])


@pytest.fixture
def add_outgroup(tmp_path):
    config_path, config = make_config(PIPELINE, tmp_path, image=find_test_image(), input_hal=mammals_hal())
    return config_path, config, tmp_path


@pytest.fixture
def prepped(add_outgroup):
    config_path, _, work = add_outgroup
    rc, output = run_prep(PIPELINE, config_path, work)
    assert rc == 0, output
    return add_outgroup


def test_dry_run_without_prep_fails(add_outgroup):
    config_path, _, work = add_outgroup
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc != 0
    assert "No prep manifest found" in output


def test_prep_records_image_only(prepped):
    _, config, _ = prepped
    manifest = PREPLIB.readManifest(PREPLIB.manifestPath(config["output_dir"]))
    assert manifest["pipeline"] == PIPELINE
    assert manifest["cactus_image"] == config["cactus_path"]
    assert manifest["generated_files"] == {}
    assert manifest["prepare_command"] is None


def test_dry_run_matches_baseline(prepped):
    # The baseline plus the new make_input_files job, which replaced writing the seqfiles at parse time
    config_path, _, work = prepped
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output
    assert job_counts(output) == {**BASELINE_JOBS, "make_input_files": 1}


def test_make_input_files_runs_once(prepped):
    config_path, config, work = prepped
    rc, output = make_input_files(config_path, work)
    assert rc == 0, output

    # Same trees as the seqfiles the old parse-time code wrote for this config
    for name, tracked in TRACKED_INPUT_FILES.items():
        assert first_line(os.path.join(config["output_dir"], name)) == first_line(tracked)

    # Before, these files were rewritten on every parse, and preprocess takes them as input, so it was
    # rescheduled on every resume. Now nothing rewrites them and the plan is back to the baseline.
    files = [os.path.join(config["output_dir"], name) for name in TRACKED_INPUT_FILES]
    before = [file_state(f) for f in files]
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output
    assert job_counts(output) == BASELINE_JOBS
    assert [file_state(f) for f in files] == before


def test_changed_branch_length_reruns_make_input_files(prepped):
    config_path, config, work = prepped
    rc, output = make_input_files(config_path, work)
    assert rc == 0, output

    # Branch lengths aren't part of this pipeline's prep, but they are params of make_input_files
    config_path, _ = make_config(PIPELINE, work, image=config["cactus_path"], input_hal=config["input_hal"],
                                 branch_length_from_new_genome=0.2)
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output
    assert job_counts(output) == {**BASELINE_JOBS, "make_input_files": 1}
