#############################################################################
# Tier-3 tests: full runs of every pipeline on the tracked datasets, with real
# Cactus jobs. Opt-in only (CACTUS_SMK_RUN_E2E=1): they submit cluster jobs and
# take hours. The Snakemake arguments come from $CACTUS_SMK_E2E_ARGS (default
# "-e slurm -j 20"). The tracked configs leave partitions blank, which the
# pipelines only accept with the slurm executor; add
# --slurm-partition-config <config> to have it choose partitions for each job.
#
# Mammals (tests/evolverMammals): align runs first, and its HAL is the input for
# add-genome, replace-genome and add-outgroup. Yeast (tests/yeast-minigraph):
# minigraph. Outputs go under pytest's tmp_path; the tracked files are only read.
#
# After each pipeline finishes, a dry-run must report nothing to do. Before the
# prep step, resumed runs could reschedule work because prep files were
# rewritten on every parse.
#############################################################################

import os
import re
import shlex
import subprocess

import pytest

from tests.helpers import dry_run, find_test_image, make_config, run_prep, run_snakemake

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(os.environ.get("CACTUS_SMK_RUN_E2E") != "1",
                       reason="set CACTUS_SMK_RUN_E2E=1 to run full pipelines (submits cluster jobs; takes hours)"),
]

E2E_ARGS = shlex.split(os.environ.get("CACTUS_SMK_E2E_ARGS", "-e slurm -j 20"))
NOTHING_TO_DO = "Nothing to be done"

MAMMALS_GENOMES = ["simCow_chr6", "simDog_chr6", "simHuman_chr6", "simMouse_chr6", "simRat_chr6"]
MAMMALS_ANCESTORS = ["Anc0", "Anc1", "Anc2", "mr"]


def run_pipeline(pipeline, work, image, **overrides):
    """Prep and fully run a pipeline, then dry-run it again; returns (config, resume dry-run output)."""
    config_path, config = make_config(pipeline, work, image=image, **overrides)

    rc, output = run_prep(pipeline, config_path, work)
    assert rc == 0, output

    rc, output = run_snakemake(pipeline, config_path, work, E2E_ARGS)
    assert rc == 0, output[-5000:]

    rc, resume_output = dry_run(pipeline, config_path, work)
    assert rc == 0, resume_output
    return config, resume_output


def output_hal(config):
    return os.path.join(config["output_dir"], f"{config['final_prefix']}.hal")


def output_mafs(config):
    prefix = os.path.join(config["output_dir"], f"{config['final_prefix']}.{config['maf_reference']}")
    return [f"{prefix}.maf.gz", f"{prefix}.nodupes.maf.gz"]


def assert_non_empty(paths):
    for path in paths:
        assert os.path.isfile(path), f"missing output {path}"
        assert os.path.getsize(path) > 0, f"empty output {path}"


def hal_tree(image, hal):
    # The Newick tree stored in a HAL file, read with halStats from the same image the pipelines ran
    result = subprocess.run(["singularity", "exec", "--cleanenv", image, "halStats", "--tree", hal],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.strip()


def branch_length(tree, name):
    match = re.search(rf"[(,]{re.escape(name)}:([0-9.eE+-]+)", tree)
    assert match, f"{name} with a branch length not found in {tree}"
    return float(match.group(1))


@pytest.fixture(scope="module")
def image():
    return find_test_image()


@pytest.fixture(scope="module")
def mammals_alignment(tmp_path_factory, image):
    return run_pipeline("align", tmp_path_factory.mktemp("align"), image)

#############################################################################
# Mammals

def test_align(mammals_alignment, image):
    config, resume_output = mammals_alignment
    assert_non_empty([output_hal(config)] + output_mafs(config))

    tree = hal_tree(image, output_hal(config))
    for genome in MAMMALS_GENOMES + MAMMALS_ANCESTORS:
        assert genome in tree

    assert NOTHING_TO_DO in resume_output


def test_add_genome(tmp_path, mammals_alignment, image):
    align_config, _ = mammals_alignment
    config, resume_output = run_pipeline("add-genome", tmp_path, image, input_hal=output_hal(align_config))
    assert_non_empty([output_hal(config)] + output_mafs(config))

    # The new leaf gets new_branch_length (the halAddToBranch fix), and the new ancestor sits
    # top_branch_length below its parent
    tree = hal_tree(image, output_hal(config))
    assert branch_length(tree, config["new_genome_name"]) == pytest.approx(config["new_branch_length"])
    assert branch_length(tree, config["new_anc_node"]) == pytest.approx(config["top_branch_length"])

    assert NOTHING_TO_DO in resume_output


def test_replace_genome(tmp_path, mammals_alignment, image):
    align_config, _ = mammals_alignment
    config, resume_output = run_pipeline("replace-genome", tmp_path, image, input_hal=output_hal(align_config))
    assert_non_empty([output_hal(config)] + output_mafs(config))

    tree = hal_tree(image, output_hal(config))
    assert config["new_genome_name"] in tree
    assert config["replace"] not in tree

    assert NOTHING_TO_DO in resume_output


def test_add_outgroup(tmp_path, mammals_alignment, image):
    align_config, _ = mammals_alignment
    config, resume_output = run_pipeline("add-outgroup", tmp_path, image, input_hal=output_hal(align_config))
    assert_non_empty([output_hal(config)] + output_mafs(config))

    # The old root and the new genome are joined under the new root
    tree = hal_tree(image, output_hal(config))
    assert re.search(rf"\){re.escape(config['new_root_name'])};?$", tree), tree
    assert branch_length(tree, config["new_genome_name"]) == pytest.approx(config["branch_length_from_new_genome"])
    assert branch_length(tree, config["old_root_name"]) == pytest.approx(config["branch_length_from_old_root"])

    assert NOTHING_TO_DO in resume_output

#############################################################################
# Yeast

def test_minigraph(tmp_path, image):
    config, resume_output = run_pipeline("minigraph", tmp_path, image)

    # The tracked config uses join_graph_type "clip", whose outputs have no suffix
    final_dir = os.path.join(config["output_dir"], config["join_graph_type"])
    prefix = os.path.join(final_dir, config["prefix"])
    assert_non_empty([f"{prefix}.full.hal", f"{prefix}.gfa.gz", f"{prefix}.vcf.gz", f"{prefix}.gbz"])

    assert NOTHING_TO_DO in resume_output
