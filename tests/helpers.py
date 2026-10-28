#############################################################################
# Shared helpers for the cactus-snakemake test suite.
#
# Every test is built on the two datasets already tracked under tests/:
#   tests/evolverMammals/  - align, add-genome, replace-genome, add-outgroup
#   tests/yeast-minigraph/ - minigraph
# Tests only ever read those files. Anything a test needs to change (output
# paths, relative genome paths) is written to a copy under pytest's tmp_path,
# never back into tests/.
#############################################################################

import glob
import os
import shutil
import subprocess
import sys

import pytest
import yaml

import lib.cactuslib as CACTUSLIB

REPO_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
MAMMALS_DIR = os.path.join(REPO_ROOT, "tests", "evolverMammals")
YEAST_DIR = os.path.join(REPO_ROOT, "tests", "yeast-minigraph")

SNAKEFILES = {
    "align": os.path.join(REPO_ROOT, "cactus.smk"),
    "add-genome": os.path.join(REPO_ROOT, "cactus_update.smk"),
    "replace-genome": os.path.join(REPO_ROOT, "cactus_replace.smk"),
    "add-outgroup": os.path.join(REPO_ROOT, "cactus_add_outgroup.smk"),
    "minigraph": os.path.join(REPO_ROOT, "cactus_minigraph.smk"),
}

FIXTURE_CONFIGS = {
    "align": os.path.join(MAMMALS_DIR, "evolverMammals-cfg.yaml"),
    "add-genome": os.path.join(MAMMALS_DIR, "evolverMammals-update-cfg.yaml"),
    "replace-genome": os.path.join(MAMMALS_DIR, "evolverMammals-replace-cfg.yaml"),
    "add-outgroup": os.path.join(MAMMALS_DIR, "evolverMammals-add-outgroup-cfg.yaml"),
    "minigraph": os.path.join(YEAST_DIR, "yeast-minigraph-cfg.yaml"),
}

# Config keys that hold paths. The tracked configs give these relative to their own
# dataset directory (they were written to be run from inside it), so make_config()
# turns them into absolute paths before a test runs Snakemake from somewhere else.
PATH_KEYS = ("input_file", "input_hal", "new_genome_fasta")

# Invoke the actual `snakemake` console-script entry point, not `python -m snakemake`.
# lib/cactuslib.py's pipelineSetup() decides whether it is the top-level run by checking
# for "__main__.py" in sys.argv[0], which `python -m snakemake` always sets. A run
# misclassified that way skips the top-level setup and looks for state that a real
# top-level run would have written first.
SNAKEMAKE_EXE = os.path.join(os.path.dirname(sys.executable), "snakemake")


def find_test_image():
    """Absolute path to a real, non-GPU Cactus image for tests that run containers.

    $CACTUS_SMK_TEST_IMAGE wins; otherwise the newest cactus_v*.sif already in one
    of the dataset directories is used. Skips if there is no image or no singularity.
    """
    if shutil.which("singularity") is None:
        pytest.skip("singularity is not on PATH")

    # An explicitly requested image that is missing is an error, not a skip
    image = os.environ.get("CACTUS_SMK_TEST_IMAGE", "")
    if image:
        if not os.path.isfile(image):
            pytest.fail(f"CACTUS_SMK_TEST_IMAGE is set, but {image} does not exist")
        return os.path.abspath(image)

    candidates = []
    for dataset_dir in (MAMMALS_DIR, YEAST_DIR):
        for image_path in glob.glob(os.path.join(dataset_dir, "cactus_v*.sif")):
            if "-gpu" not in os.path.basename(image_path):
                candidates.append(image_path)

    if not candidates:
        pytest.skip("No non-GPU cactus_v*.sif found in the dataset directories; set CACTUS_SMK_TEST_IMAGE")

    return max(candidates, key=lambda p: CACTUSLIB.parseCactusVersion(os.path.basename(p)))


def mammals_hal():
    """The evolverMammals HAL that add-genome, replace-genome and add-outgroup start from.

    It is produced by running the align pipeline on the mammals dataset and is not
    tracked in git, so tests that need it skip when it isn't there. Read-only.
    """
    hal = os.environ.get("CACTUS_SMK_TEST_HAL", os.path.join(MAMMALS_DIR, "evolverMammals-out", "evolverMammals.hal"))
    if not os.path.isfile(hal):
        pytest.skip(f"evolverMammals HAL not found at {hal}; set CACTUS_SMK_TEST_HAL")
    return os.path.abspath(hal)


def copy_seqfile_abs(src, dst):
    """Copy a Cactus input file, making relative genome paths absolute.

    The file is a Newick tree on the first line, then name<TAB>path lines. Relative
    paths are resolved against the source file's directory; nothing else changes.
    """
    src_dir = os.path.dirname(os.path.abspath(src))
    with open(src) as infile, open(dst, "w") as outfile:
        first = True
        for line in infile:
            if first or not line.strip():
                outfile.write(line)
                first = False
                continue

            fields = line.rstrip("\n").split("\t")
            if not os.path.isabs(fields[1]):
                fields[1] = os.path.normpath(os.path.join(src_dir, fields[1]))
            outfile.write("\t".join(fields) + "\n")

    return dst


def make_config(pipeline, tmp_path, image=None, **overrides):
    """Build a test config from a pipeline's tracked fixture config.

    Writes it to tmp_path/config.yaml and returns (config path, config dict).
      - output_dir and tmp_dir are pointed into tmp_path
      - relative paths in PATH_KEYS become absolute (relative to the dataset directory)
      - cactus_path is set to the test image when one is given, so nothing is downloaded
      - overwrite_original_hal is always False, so the shared mammals HAL is never edited
      - for align, input_file is a copy of the tracked one with absolute genome paths
    """
    fixture_cfg = FIXTURE_CONFIGS[pipeline]
    dataset_dir = os.path.dirname(fixture_cfg)
    with open(fixture_cfg) as f:
        config = yaml.safe_load(f)

    for key in PATH_KEYS:
        if config.get(key) and not os.path.isabs(config[key]):
            config[key] = os.path.normpath(os.path.join(dataset_dir, config[key]))

    config["output_dir"] = str(tmp_path / "out")
    config["tmp_dir"] = str(tmp_path / "tmp")

    if image:
        config["cactus_path"] = image

    if "overwrite_original_hal" in config:
        config["overwrite_original_hal"] = False

    if pipeline == "align":
        config["input_file"] = copy_seqfile_abs(config["input_file"], str(tmp_path / os.path.basename(config["input_file"])))

    config.update(overrides)

    # Guard against an override undoing the protection above
    if config.get("overwrite_original_hal"):
        raise ValueError("Tests must never set overwrite_original_hal: True; the mammals HAL is shared.")

    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f)

    return str(config_path), config


def run_snakemake(pipeline, config_path, cwd, args=(), env=None):
    """Run Snakemake on one pipeline from cwd; returns (exit code, output).

    stdout and stderr are combined: which stream a parse-time error lands on has
    changed between Snakemake versions.
    """
    cmd = [SNAKEMAKE_EXE, "-s", SNAKEFILES[pipeline], "--configfile", str(config_path), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd), env=env)
    return result.returncode, result.stdout + result.stderr


def dry_run(pipeline, config_path, cwd, args=()):
    """A Snakemake dry-run of one pipeline.

    -e slurm is passed because the tracked configs leave partitions blank, which
    getResources() only accepts for the slurm/cannon executors. Nothing is submitted
    in a dry-run.
    """
    return run_snakemake(pipeline, config_path, cwd, ["-n", "-e", "slurm", *args])


def job_counts(output):
    """Parse the "Job stats:" table of a dry-run into {rule: count}, without "total".

    The table is "Job stats:", a header row, a dashed rule, then one row per rule.
    Returns {} if the output has no table.
    """
    counts = {}
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if line.strip() != "Job stats:":
            continue

        for row in lines[i + 3:]:
            fields = row.split()
            if len(fields) != 2 or not fields[1].isdigit() or fields[0] == "total":
                break
            counts[fields[0]] = int(fields[1])
        break

    return counts
