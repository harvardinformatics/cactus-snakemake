#############################################################################
# Tier-1 tests for lib/cactuslib.py: Singularity bind-path parsing, the singularity
# command prefixes, preprocess seqfile copies, Cactus version tag ordering, and
# per-rule resource lookup.
#
# Resource tests use the rule_resources block of the tracked align config,
# tests/evolverMammals/evolverMammals-cfg.yaml (read-only).
#############################################################################

import copy
import os
import shutil

import pytest
import yaml

import lib.cactuslib as CACTUSLIB
from tests.helpers import FIXTURE_CONFIGS, MAMMALS_DIR, YEAST_DIR

#############################################################################
# parseSingularityBindPaths

def test_bind_paths_blank():
    assert CACTUSLIB.parseSingularityBindPaths(None) == []
    assert CACTUSLIB.parseSingularityBindPaths("") == []
    assert CACTUSLIB.parseSingularityBindPaths([]) == []


def test_bind_paths_valid_and_deduplicated():
    bind_paths = [MAMMALS_DIR, f"{YEAST_DIR}:/yeast:ro", MAMMALS_DIR]
    assert CACTUSLIB.parseSingularityBindPaths(bind_paths) == ["--bind", MAMMALS_DIR, "--bind", f"{YEAST_DIR}:/yeast:ro"]


@pytest.mark.parametrize("bind_paths, message", [
    (MAMMALS_DIR, "must be a YAML list"),
    ([1], "must be a string"),
    (["  "], "cannot be blank"),
    ([f"{MAMMALS_DIR}:/a:ro:extra"], "Expected src[:dest[:opts]]"),
    (["tests/evolverMammals"], "must be absolute"),
    ([f"{MAMMALS_DIR}:relative/dest"], "destination path must be absolute"),
    ([f"{MAMMALS_DIR}:/dest:rx"], "Use 'ro' or 'rw'"),
])
def test_bind_paths_invalid(bind_paths, message):
    with pytest.raises(ValueError, match=message.replace("[", r"\[").replace("]", r"\]")):
        CACTUSLIB.parseSingularityBindPaths(bind_paths)


def test_bind_paths_missing_source(tmp_path):
    missing = str(tmp_path / "does-not-exist")
    with pytest.raises(ValueError, match="does not exist"):
        CACTUSLIB.parseSingularityBindPaths([missing])

#############################################################################
# buildCactusCommands (only builds command lists; the image name is never opened)

def test_cactus_commands_cpu():
    cactus_path, cactus_path_tmp = CACTUSLIB.buildCactusCommands("cactus_v3.2.1.sif", False, "/scratch/cactus-tmp", [MAMMALS_DIR])
    assert cactus_path == ["singularity", "exec", "--cleanenv", "--bind", MAMMALS_DIR, "cactus_v3.2.1.sif"]
    # Only the tmp variant binds the host tmp dir to /tmp, after any user bind paths
    assert cactus_path_tmp == ["singularity", "exec", "--cleanenv", "--bind", MAMMALS_DIR,
                               "--bind", "/scratch/cactus-tmp:/tmp", "cactus_v3.2.1.sif"]


def test_cactus_commands_gpu():
    cactus_path, cactus_path_tmp = CACTUSLIB.buildCactusCommands("cactus_v3.2.1-gpu.sif", True, "/scratch/cactus-tmp", [])
    assert cactus_path == ["singularity", "exec", "--nv", "--cleanenv", "cactus_v3.2.1-gpu.sif"]
    assert cactus_path_tmp[:3] == ["singularity", "exec", "--nv"]

#############################################################################
# preprocessSeqFile (uses the tracked cactus-prepare output as the seqfile)

def test_preprocess_seqfile_copy(tmp_path):
    seqfile = tmp_path / "evolverMammals.txt"
    shutil.copyfile(os.path.join(MAMMALS_DIR, "evolverMammals-out", "evolverMammals.txt"), seqfile)
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    copy = CACTUSLIB.preprocessSeqFile(str(seqfile), str(log_dir), "simCow.chr6")

    # cactus-preprocess gets this copy to rewrite; the original is a different file
    assert copy == str(log_dir / "simCow.chr6.preprocess.seqfile.txt")
    assert open(copy).read() == seqfile.read_text()
    assert not os.path.samefile(copy, seqfile)

#############################################################################
# parseCactusVersion

def test_cactus_version_ordering():
    assert CACTUSLIB.parseCactusVersion("v3.1.2-gpu") == (3, 1, 2)
    tags = ["v3.0.1", "v3.2.1", "v3.1.13", "v3.1.4"]
    assert max(tags, key=CACTUSLIB.parseCactusVersion) == "v3.2.1"
    # Numeric, not string, comparison
    assert CACTUSLIB.parseCactusVersion("v3.1.13") > CACTUSLIB.parseCactusVersion("v3.1.4")

#############################################################################
# getResources

@pytest.fixture
def align_config():
    with open(FIXTURE_CONFIGS["align"]) as f:
        return yaml.safe_load(f)


def test_resources_for_rule(align_config):
    resources = CACTUSLIB.getResources(align_config, "slurm", "blast")
    # A blank partition is allowed for the slurm/cannon executors, which pick one themselves
    assert resources == {"slurm_partition": "", "mem_mb": 50000, "cpus_per_task": 24, "runtime": 120}


def test_resources_fall_back_to_default(align_config):
    # The align config has no copy_input entry, so every value comes from "default"
    resources = CACTUSLIB.getResources(align_config, "slurm", "copy_input")
    assert resources == {"slurm_partition": "", "mem_mb": 30000, "cpus_per_task": 8, "runtime": 60}


def test_resources_missing_partition_without_slurm(align_config):
    with pytest.raises(ValueError):
        CACTUSLIB.getResources(align_config, "none", "blast")


def test_resources_per_attempt_schedule(align_config):
    config = copy.deepcopy(align_config)
    config["rule_resources"]["blast"]["mem_mb"] = [50000, 100000]
    mem_mb = CACTUSLIB.getResources(config, "slurm", "blast")["mem_mb"]

    # A list becomes a function of the attempt number; attempts past the end reuse the last value
    assert callable(mem_mb)
    assert [mem_mb(None, attempt=a) for a in (1, 2, 3)] == [50000, 100000, 100000]


def test_resources_empty_schedule(align_config):
    config = copy.deepcopy(align_config)
    config["rule_resources"]["blast"]["mem_mb"] = []
    with pytest.raises(ValueError, match="cannot be empty"):
        CACTUSLIB.getResources(config, "slurm", "blast")
