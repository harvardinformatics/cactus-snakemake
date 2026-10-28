#############################################################################
# Tier-2 tests for the add-genome pipeline's prep step (cactus_add_genome.smk +
# lib/preplib.py): real cactus-update-prepare runs in a container and real
# Snakemake dry-runs, adding simGorilla to the evolverMammals HAL as configured in
# tests/evolverMammals/evolverMammals-update-cfg.yaml. Needs singularity, a local
# Cactus image and the evolverMammals HAL (see tests/helpers.py); skips otherwise.
# The HAL is only read: test configs always set overwrite_original_hal: False.
#
# BASELINE_JOBS was captured from the pre-refactor pipeline (v3.5.0, which ran
# cactus-update-prepare on every parse) dry-running the same dataset.
#############################################################################

import os

import pytest

import lib.preplib as PREPLIB
from tests.helpers import (MAMMALS_DIR, dry_run, file_state, find_test_image, first_line, job_counts,
                           make_config, mammals_hal, run_prep)

pytestmark = pytest.mark.prep

PIPELINE = "add-genome"

BASELINE_JOBS = {
    "add_to_branch": 1, "align_new_genome": 1, "align_parent": 1, "all": 1, "append_subtrees": 1,
    "blast_new_genome": 1, "blast_parent": 1, "convert_new_genome": 1, "copy_or_get_hal": 1, "maf": 1,
    "preprocess": 1,
}

# Real cactus-update-prepare output for this config, from an earlier run
TRACKED_SEQ_OUT = os.path.join(MAMMALS_DIR, "evolverMammals-update-out", "seq_file.out")

PREP_FILES = ["cactus-update-input.txt", "seq_file.in", "seq_file.out"]


def prep_files(config):
    # The files prep writes, and the manifest
    return [os.path.join(config["output_dir"], f) for f in PREP_FILES] + [PREPLIB.manifestPath(config["output_dir"])]


@pytest.fixture
def add_genome(tmp_path):
    config_path, config = make_config(PIPELINE, tmp_path, image=find_test_image(), input_hal=mammals_hal())
    return config_path, config, tmp_path


@pytest.fixture
def prepped(add_genome):
    config_path, _, work = add_genome
    rc, output = run_prep(PIPELINE, config_path, work)
    assert rc == 0, output
    return add_genome


def test_dry_run_without_prep_fails(add_genome):
    config_path, _, work = add_genome
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc != 0
    assert "No prep manifest found" in output


def test_prep_writes_seqfiles_and_manifest(prepped):
    _, config, _ = prepped

    # The new ancestor splits the mr branch exactly as in the earlier real run
    seq_out = os.path.join(config["output_dir"], "seq_file.out")
    assert first_line(seq_out) == first_line(TRACKED_SEQ_OUT)

    manifest = PREPLIB.readManifest(PREPLIB.manifestPath(config["output_dir"]))
    assert manifest["pipeline"] == PIPELINE
    assert sorted(manifest["generated_files"]) == sorted(PREP_FILES)


def test_dry_run_matches_baseline(prepped):
    config_path, _, work = prepped
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output
    assert job_counts(output) == BASELINE_JOBS


def test_dry_run_changes_nothing(prepped):
    # Before the prep step, every parse rewrote these files, and preprocess takes the
    # seqfiles as input, so it was rescheduled on every resume
    config_path, config, work = prepped
    files = prep_files(config)
    before = [file_state(f) for f in files]

    for _ in range(2):
        rc, output = dry_run(PIPELINE, config_path, work)
        assert rc == 0, output

    assert [file_state(f) for f in files] == before


def test_prep_again_is_noop(prepped):
    config_path, config, work = prepped
    files = prep_files(config)
    before = [file_state(f) for f in files]

    rc, output = run_prep(PIPELINE, config_path, work)
    assert rc == 0, output
    assert "Prep is already up to date" in output
    assert [file_state(f) for f in files] == before


def test_changed_placement_is_stale_until_forced(prepped):
    config_path, config, work = prepped

    # Move the new ancestor further down the mr branch
    config_path, config = make_config(PIPELINE, work, image=config["cactus_path"], input_hal=config["input_hal"],
                                      top_branch_length=0.05)

    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc != 0
    assert "top_branch_length: was 0.1 at prep, config now has 0.05" in output

    rc, output = run_prep(PIPELINE, config_path, work, "prep_force=T")
    assert rc == 0, output
    assert "AncGorilla:0.05" in first_line(os.path.join(config["output_dir"], "seq_file.out"))

    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output


def test_skip_prepare_warns(prepped):
    config_path, config, work = prepped
    config_path, _ = make_config(PIPELINE, work, image=config["cactus_path"], input_hal=config["input_hal"],
                                 skip_prepare=True)
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output
    assert "skip_prepare is no longer used" in output
