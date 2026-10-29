#############################################################################
# Tier-1 tests for lib/preplib.py: the fingerprint and manifest checks that decide
# whether a pipeline's prep is missing, current, or stale. Running prep itself
# (cactus-prepare in a container) is covered by the tier-2 tests in tests/pipeline/.
#
# Fixtures (tracked, read-only; copied into tmp_path wherever a test edits them):
#   tests/evolverMammals/evolverMammals-cfg.yaml               - align config
#   tests/evolverMammals/evolverMammals.txt                    - align input file
#   tests/evolverMammals/evolverMammals-out/evolverMammals.txt - real cactus-prepare output
#############################################################################

import hashlib
import os
import shutil

import pytest

import lib.preplib as PREPLIB
from tests.helpers import MAMMALS_DIR, make_config

CACTUS_FILE = os.path.join(MAMMALS_DIR, "evolverMammals-out", "evolverMammals.txt")


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.fixture
def align(tmp_path):
    # An align config whose output directory holds a copy of the real cactus-prepare output
    _, config = make_config("align", tmp_path)
    os.makedirs(config["output_dir"])
    seqfile = shutil.copy(CACTUS_FILE, config["output_dir"])
    return config, seqfile

#############################################################################
# Fingerprints

def test_fingerprint_align(align):
    config, _ = align
    assert PREPLIB.fingerprint("align", config) == {
        "cactus_path": "download",
        "use_gpu": False,
        "input_file_sha256": sha256(config["input_file"]),
    }


def test_fingerprint_unchanged(align):
    config, _ = align
    fp = PREPLIB.fingerprint("align", config)
    assert PREPLIB.compareFingerprint(fp, PREPLIB.fingerprint("align", config)) == []


def test_fingerprint_input_file_edited(align):
    config, _ = align
    prepped_fp = PREPLIB.fingerprint("align", config)

    # Change one branch length in the tree of the copied input file
    with open(config["input_file"]) as f:
        text = f.read()
    with open(config["input_file"], "w") as f:
        f.write(text.replace("simHuman_chr6:0.144018", "simHuman_chr6:0.2", 1))

    assert PREPLIB.compareFingerprint(prepped_fp, PREPLIB.fingerprint("align", config)) == [
        "input_file: contents have changed since prep"
    ]


@pytest.mark.parametrize("key, value", [("cactus_path", "3.2.1"), ("use_gpu", True)])
def test_fingerprint_config_changed(align, key, value):
    config, _ = align
    prepped_fp = PREPLIB.fingerprint("align", config)
    mismatches = PREPLIB.compareFingerprint(prepped_fp, PREPLIB.fingerprint("align", {**config, key: value}))
    assert len(mismatches) == 1
    assert mismatches[0].startswith(f"{key}: ")

def test_fingerprint_add_genome(tmp_path):
    _, config = make_config("add-genome", tmp_path)
    assert PREPLIB.fingerprint("add-genome", config) == {
        "cactus_path": "download",
        "use_gpu": False,
        "input_hal": os.path.join(MAMMALS_DIR, "evolverMammals-align-out", "evolverMammals.hal"),
        "new_genome_fasta": os.path.join(MAMMALS_DIR, "evolverMammals-seq", "simGorilla.chr6"),
        "new_genome_name": "simGorilla",
        "new_branch_length": 0.075,
        "parent_node": "Anc1",
        "child_node": "mr",
        "new_anc_node": "AncGorilla",
        "top_branch_length": 0.1,
    }


def test_fingerprint_replace_genome(tmp_path):
    _, config = make_config("replace-genome", tmp_path)
    assert PREPLIB.fingerprint("replace-genome", config) == {
        "cactus_path": "download",
        "use_gpu": False,
        "input_hal": os.path.join(MAMMALS_DIR, "evolverMammals-align-out", "evolverMammals.hal"),
        "new_genome_fasta": os.path.join(MAMMALS_DIR, "evolverMammals-seq", "simGorilla.chr6"),
        "replace": "simHuman_chr6",
        "new_genome_name": "simGorilla_chr6",
    }


@pytest.mark.parametrize("pipeline, cactus_path", [("add-outgroup", "download"), ("minigraph", "download")])
def test_fingerprint_image_only(tmp_path, pipeline, cactus_path):
    # These pipelines have no prepare step, so prep only depends on the cactus image settings
    _, config = make_config(pipeline, tmp_path)
    assert PREPLIB.fingerprint(pipeline, config) == {"cactus_path": cactus_path, "use_gpu": False}


def test_minigraph_never_uses_gpu(tmp_path):
    # cactus_minigraph.smk always runs the CPU image, so prep must resolve that one
    _, config = make_config("minigraph", tmp_path, use_gpu=True)
    assert PREPLIB.usesGpu("minigraph", config) is False
    assert PREPLIB.fingerprint("minigraph", config)["use_gpu"] is False


def test_fingerprint_hal_by_path_only(tmp_path):
    # overwrite_original_hal edits the input HAL during a run, so its contents can't be
    # fingerprinted; the path is used without opening the file (this one is never created)
    hal = str(tmp_path / "never-created.hal")
    _, config = make_config("add-genome", tmp_path, input_hal=hal)
    assert PREPLIB.fingerprint("add-genome", config)["input_hal"] == hal


def test_seqfile_names():
    seq_out = os.path.join(MAMMALS_DIR, "evolverMammals-update-out", "seq_file.out")
    assert PREPLIB.readSeqfileNames(seq_out) == ["mr", "simGorilla", "simHuman_chr6", "Anc1", "AncGorilla"]

#############################################################################
# Files written by prep

def test_generated_files_unchanged(align):
    config, seqfile = align
    generated = {"evolverMammals.txt": sha256(seqfile)}
    assert PREPLIB.checkGeneratedFiles(generated, config["output_dir"]) == []


def test_generated_files_modified(align):
    config, seqfile = align
    generated = {"evolverMammals.txt": sha256(seqfile)}
    with open(seqfile, "a") as f:
        f.write("\n")
    assert PREPLIB.checkGeneratedFiles(generated, config["output_dir"]) == [
        "evolverMammals.txt: has been modified since prep"
    ]


def test_generated_files_missing(align):
    # A manifest entry for a file that was never written to this output directory
    config, _ = align
    assert PREPLIB.checkGeneratedFiles({"seq_file.out": "0" * 64}, config["output_dir"]) == [
        "seq_file.out: written by prep, but no longer exists"
    ]

#############################################################################
# Manifests

def test_manifest_round_trip(align):
    config, seqfile = align
    manifest = PREPLIB.buildManifest("align", config, "/images/cactus_v3.2.1.sif", "v3.2.1",
                                     ["cactus-prepare", config["input_file"]], [seqfile], config["output_dir"])

    assert manifest["generated_files"] == {"evolverMammals.txt": sha256(seqfile)}
    assert manifest["prepare_command"] == f"cactus-prepare {config['input_file']}"
    assert manifest["fingerprint"] == PREPLIB.fingerprint("align", config)

    manifest_file = PREPLIB.manifestPath(config["output_dir"])
    PREPLIB.writeManifest(manifest, manifest_file)
    assert PREPLIB.readManifest(manifest_file) == manifest


def test_check_manifest_other_pipeline(align):
    config, seqfile = align
    manifest = PREPLIB.buildManifest("align", config, "/images/cactus_v3.2.1.sif", "v3.2.1", None, [seqfile], config["output_dir"])
    mismatches = PREPLIB.checkManifest(manifest, "minigraph", config, config["output_dir"])
    assert len(mismatches) == 1
    assert mismatches[0].startswith("pipeline: ")


def test_check_manifest_image_gone(align):
    # The recorded image path does not exist (no file is created for it)
    config, seqfile = align
    image = os.path.join(config["output_dir"], "cactus_v3.2.1.sif")
    manifest = PREPLIB.buildManifest("align", config, image, "v3.2.1", None, [seqfile], config["output_dir"])
    assert PREPLIB.checkManifest(manifest, "align", config, config["output_dir"]) == [
        f"cactus_image: {image} no longer exists"
    ]


def test_require_prep_without_manifest(align, caplog):
    config, _ = align
    with pytest.raises(SystemExit):
        PREPLIB.requirePrep("align", config, config["output_dir"], True, 50, "cactus.smk", ["my-config.yaml"])
    assert "No prep manifest found" in caplog.text
    # The wrapper command (next to the Snakefile) and the plain snakemake command
    assert "cactus_snakemake prep align --configfile my-config.yaml" in caplog.text
    assert "snakemake -s cactus.smk --configfile my-config.yaml --config prep=T" in caplog.text
