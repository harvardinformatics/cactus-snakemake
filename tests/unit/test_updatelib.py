#############################################################################
# Tier-1 tests for lib/updatelib.py: the parsing of cactus-update-prepare output
# used by the add-genome (cactus_add_genome.smk) and replace-genome (cactus_replace_genome.smk)
# pipelines, and the input files the add-outgroup pipeline writes for itself.
#
# Fixtures (tracked, read-only), all under tests/evolverMammals/:
#   evolverMammals-update-out/seq_file.out  - real cactus-update-prepare output (add-genome)
#   evolverMammals-replace-out/seq_file.out - real cactus-update-prepare output (replace)
#   evolverMammals-add-out/add-outgroup-{pre,post}.txt - files written by add-outgroup
#   evolverMammals-add-outgroup-cfg.yaml    - the config those files came from
#############################################################################

import os

import pytest
import yaml

import lib.updatelib as UPDATELIB
from tests.helpers import MAMMALS_DIR

UPDATE_SEQ_OUT = os.path.join(MAMMALS_DIR, "evolverMammals-update-out", "seq_file.out")
REPLACE_SEQ_OUT = os.path.join(MAMMALS_DIR, "evolverMammals-replace-out", "seq_file.out")
ADD_OUTGROUP_CFG = os.path.join(MAMMALS_DIR, "evolverMammals-add-outgroup-cfg.yaml")
ADD_OUTGROUP_PRE = os.path.join(MAMMALS_DIR, "evolverMammals-add-out", "add-outgroup-pre.txt")
ADD_OUTGROUP_POST = os.path.join(MAMMALS_DIR, "evolverMammals-add-out", "add-outgroup-post.txt")


def read_seqfile(path):
    # (tree line, [(name, path), ...]) for a Cactus seqfile
    with open(path) as f:
        lines = [line.strip() for line in f if line.strip()]
    return lines[0], [tuple(line.split("\t")) for line in lines[1:]]

#############################################################################
# cactus-update-prepare output

def test_replace_new_genome_and_ancestor():
    new_genome_file, ancestor = UPDATELIB.getGenomesToAddReplace(REPLACE_SEQ_OUT, "simGorilla_chr6")
    assert os.path.basename(new_genome_file) == "simGorilla.chr6"
    assert ancestor == "Anc1"


def test_add_genome_new_genome_file():
    new_genome_file, _ = UPDATELIB.getGenomesToAddReplace(UPDATE_SEQ_OUT, "simGorilla")
    assert os.path.basename(new_genome_file) == "simGorilla.chr6"


def test_orig_branch_length():
    # mr's original branch length (0.271974 in tests/evolverMammals/evolverMammals.txt) is
    # split by the new ancestor into 0.171974 below it and the 0.1 top branch above it
    orig_bl = UPDATELIB.getOrigBranchLength(UPDATE_SEQ_OUT, "mr", "AncGorilla", 0.1)
    assert orig_bl == pytest.approx(0.271974)


def test_orig_branch_length_mismatch_exits():
    with pytest.raises(SystemExit):
        UPDATELIB.getOrigBranchLength(UPDATE_SEQ_OUT, "mr", "AncGorilla", 0.2)

#############################################################################
# add-outgroup input files

def test_add_outgroup_input_files(tmp_path):
    with open(ADD_OUTGROUP_CFG) as f:
        config = yaml.safe_load(f)

    # Built the same way cactus_add_outgroup.smk builds it, with output in tmp_path
    output_dir = str(tmp_path)
    genome_fasta = os.path.join(MAMMALS_DIR, config["new_genome_fasta"])
    genome_ext = os.path.splitext(genome_fasta)[1][1:]
    file_dict = {
        "new-genome": {
            "fasta-orig": genome_fasta,
            "fasta-preprocess": os.path.join(output_dir, f"{config['new_genome_name']}.{genome_ext}"),
            "name": config["new_genome_name"],
            "branch-length": config["branch_length_from_new_genome"],
        },
        "old-root": {
            "fasta": os.path.join(output_dir, f"{config['old_root_name']}.fa"),
            "name": config["old_root_name"],
            "branch-length": config["branch_length_from_old_root"],
        },
        "new-root": {
            "fasta": os.path.join(output_dir, f"{config['new_root_name']}.fa"),
            "name": config["new_root_name"],
        },
    }

    pre_file = str(tmp_path / "add-outgroup-pre.txt")
    post_file = str(tmp_path / "add-outgroup-post.txt")
    UPDATELIB.createAddOutgroupInputFiles(file_dict, pre_file, post_file, output_dir, 50)

    # Trees must match exactly; paths are compared by basename, since the tracked files
    # hold the absolute paths of the output directory they were written to
    for written, tracked in ((pre_file, ADD_OUTGROUP_PRE), (post_file, ADD_OUTGROUP_POST)):
        written_tree, written_seqs = read_seqfile(written)
        tracked_tree, tracked_seqs = read_seqfile(tracked)
        assert written_tree == tracked_tree
        assert [(n, os.path.basename(p)) for n, p in written_seqs] == [(n, os.path.basename(p)) for n, p in tracked_seqs]

    # The pre file points at the original genome FASTA, the post file at the preprocessed copy
    assert dict(read_seqfile(pre_file)[1])["simGorilla"] == genome_fasta
    assert dict(read_seqfile(post_file)[1])["simGorilla"] == os.path.join(output_dir, "simGorilla.chr6")
