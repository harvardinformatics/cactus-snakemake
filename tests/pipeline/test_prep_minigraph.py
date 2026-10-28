#############################################################################
# Tier-2 tests for the minigraph pipeline's prep step (cactus_minigraph.smk +
# lib/preplib.py), on the yeast pangenome dataset as configured in
# tests/yeast-minigraph/yeast-minigraph-cfg.yaml. Prep only resolves the image for
# this pipeline. Needs singularity and a local Cactus image (see tests/helpers.py);
# skips otherwise.
#
# BASELINE_JOBS was captured from the pre-refactor pipeline (v3.5.0) dry-running the
# same dataset. The plan stops at the split checkpoint, so it has no align jobs.
#############################################################################

import pytest

import lib.preplib as PREPLIB
from tests.helpers import dry_run, file_state, find_test_image, job_counts, make_config, run_prep

pytestmark = pytest.mark.prep

PIPELINE = "minigraph"

BASELINE_JOBS = {"all": 1, "copy_input": 1, "graphmap": 1, "join": 1, "minigraph": 1, "split": 1}


@pytest.fixture
def minigraph(tmp_path):
    config_path, config = make_config(PIPELINE, tmp_path, image=find_test_image())
    return config_path, config, tmp_path


@pytest.fixture
def prepped(minigraph):
    config_path, _, work = minigraph
    rc, output = run_prep(PIPELINE, config_path, work)
    assert rc == 0, output
    return minigraph


def test_dry_run_without_prep_fails(minigraph):
    config_path, _, work = minigraph
    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc != 0
    assert "No prep manifest found" in output


def test_prep_records_image_only(prepped):
    _, config, _ = prepped
    manifest = PREPLIB.readManifest(PREPLIB.manifestPath(config["output_dir"]))
    assert manifest["pipeline"] == PIPELINE
    assert manifest["cactus_image"] == config["cactus_path"]
    assert manifest["generated_files"] == {}
    assert manifest["fingerprint"]["use_gpu"] is False


def test_dry_run_matches_baseline(prepped):
    config_path, config, work = prepped
    manifest_file = PREPLIB.manifestPath(config["output_dir"])
    before = file_state(manifest_file)

    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc == 0, output
    assert job_counts(output) == BASELINE_JOBS
    assert file_state(manifest_file) == before


def test_prep_again_is_noop(prepped):
    config_path, config, work = prepped
    manifest_file = PREPLIB.manifestPath(config["output_dir"])
    before = file_state(manifest_file)

    rc, output = run_prep(PIPELINE, config_path, work)
    assert rc == 0, output
    assert "Prep is already up to date" in output
    assert file_state(manifest_file) == before


def test_changed_cactus_path_is_stale(prepped):
    # The Snakefile only compares the config value with the manifest; it never resolves "download" itself
    config_path, config, work = prepped
    config_path, _ = make_config(PIPELINE, work, cactus_path="download")

    rc, output = dry_run(PIPELINE, config_path, work)
    assert rc != 0
    assert f"cactus_path: was '{config['cactus_path']}' at prep, config now has 'download'" in output
