#############################################################################
# Tier-2 tests for the align pipeline's prep step (cactus.smk + lib/preplib.py):
# real cactus-prepare runs in a container and real Snakemake dry-runs, on a copy
# of the evolverMammals dataset. Needs singularity and a local Cactus image (see
# find_test_image() in tests/helpers.py); skips otherwise.
#
# BASELINE_JOBS was captured from the pre-refactor pipeline (v3.5.0, which ran
# cactus-prepare on every parse) dry-running the same dataset, so the prep step
# must produce exactly the same job plan.
#############################################################################

import os

import pytest
import yaml

import lib.preplib as PREPLIB
from tests.helpers import (MAMMALS_DIR, dry_run, file_state, find_test_image, first_line, job_counts,
                           make_config, run_prep, run_snakemake)

pytestmark = pytest.mark.prep

BASELINE_JOBS = {"align": 4, "all": 1, "append": 1, "blast": 4, "convert": 4, "copy_hal": 1, "maf": 1, "preprocess": 5}

# Real cactus-prepare output for the tracked input file, from an earlier full run
TRACKED_SEQFILE = os.path.join(MAMMALS_DIR, "evolverMammals-align-out", "evolverMammals.txt")


def prep(config_path, cwd, *extra_config):
    return run_prep("align", config_path, cwd, *extra_config)


def prep_files(config):
    # The seqfile cactus-prepare writes, and the manifest
    seqfile = os.path.join(config["output_dir"], os.path.basename(config["input_file"]))
    return seqfile, PREPLIB.manifestPath(config["output_dir"])


@pytest.fixture
def align(tmp_path):
    config_path, config = make_config("align", tmp_path, image=find_test_image())
    return config_path, config, tmp_path


@pytest.fixture
def prepped(align):
    config_path, _, work = align
    rc, output = prep(config_path, work)
    assert rc == 0, output
    return align


def test_dry_run_without_prep_fails(align):
    config_path, _, work = align
    rc, output = dry_run("align", config_path, work)
    assert rc != 0
    assert "No prep manifest found" in output
    assert "--config prep=T" in output


def test_prep_writes_seqfile_and_manifest(prepped):
    _, config, _ = prepped
    seqfile, manifest_file = prep_files(config)

    # cactus-prepare labels the tree exactly as it did in the earlier real run
    assert first_line(seqfile) == first_line(TRACKED_SEQFILE)

    manifest = PREPLIB.readManifest(manifest_file)
    assert manifest["pipeline"] == "align"
    assert manifest["cactus_image"] == config["cactus_path"]
    assert list(manifest["generated_files"]) == [os.path.basename(seqfile)]


def test_dry_run_matches_baseline(prepped):
    config_path, _, work = prepped
    rc, output = dry_run("align", config_path, work)
    assert rc == 0, output
    assert job_counts(output) == BASELINE_JOBS


def test_dry_run_changes_nothing(prepped):
    # The main fix: before the prep step, every parse re-ran cactus-prepare and rewrote the seqfile
    config_path, config, work = prepped
    files = prep_files(config)
    before = [file_state(f) for f in files]

    for _ in range(2):
        rc, output = dry_run("align", config_path, work)
        assert rc == 0, output

    assert [file_state(f) for f in files] == before


def test_preprocess_leaves_prep_files_untouched(prepped):
    # cactus-preprocess always rewrites the output seqfile it is given, so each preprocess job gets its
    # own copy (CACTUSLIB.preprocessSeqFile). This runs one real preprocess job (simCow.chr6) locally.
    config_path, config, work = prepped
    files = prep_files(config)
    before = [file_state(f) for f in files]

    # Run locally with 2 cores. The tracked config leaves partitions blank, which getResources() accepts
    # when the executor is slurm; "executor: slurm" in the config says so without -e slurm, so nothing
    # is submitted. Neither key is part of the prep fingerprint.
    config["executor"] = "slurm"
    config["rule_resources"]["preprocess"]["cpus"] = 2
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)

    target = os.path.join(config["output_dir"], "simCow.chr6")
    rc, output = run_snakemake("align", config_path, work, ["--cores", "2", target])
    assert rc == 0, output[-5000:]
    assert os.path.getsize(target) > 0

    # cactus-preprocess got (and rewrote) its own copy; the prep seqfile and manifest are untouched
    assert os.path.isfile(os.path.join(config["output_dir"], "logs", "simCow.chr6.preprocess.seqfile.txt"))
    assert [file_state(f) for f in files] == before

    # The finished preprocess job isn't scheduled again
    rc, output = dry_run("align", config_path, work)
    assert rc == 0, output
    assert job_counts(output) == {**BASELINE_JOBS, "preprocess": BASELINE_JOBS["preprocess"] - 1}


def test_prep_again_is_noop(prepped):
    config_path, config, work = prepped
    files = prep_files(config)
    before = [file_state(f) for f in files]

    rc, output = prep(config_path, work)
    assert rc == 0, output
    assert "Prep is already up to date" in output
    assert [file_state(f) for f in files] == before


def test_edited_input_is_stale_until_forced(prepped):
    config_path, config, work = prepped
    seqfile, _ = prep_files(config)

    # Change one branch length in the tree of the copied input file
    with open(config["input_file"]) as f:
        text = f.read()
    with open(config["input_file"], "w") as f:
        f.write(text.replace("simHuman_chr6:0.144018", "simHuman_chr6:0.2", 1))

    rc, output = dry_run("align", config_path, work)
    assert rc != 0
    assert "input_file: contents have changed since prep" in output

    # Prep refuses to overwrite a stale prep without prep_force
    rc, output = prep(config_path, work)
    assert rc != 0
    assert "prep_force=T" in output

    rc, output = prep(config_path, work, "prep_force=T")
    assert rc == 0, output
    assert "simHuman_chr6:0.2" in first_line(seqfile)

    rc, output = dry_run("align", config_path, work)
    assert rc == 0, output
