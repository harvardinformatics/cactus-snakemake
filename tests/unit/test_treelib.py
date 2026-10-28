#############################################################################
# Tier-1 tests for lib/treelib.py (plus cactuslib.normalizeInternalSeqs): how the
# align pipeline (cactus.smk) turns the Cactus input file and cactus-prepare's
# labeled seqfile into tips, internal nodes, alignment rounds and per-node inputs.
# The rules are generated from these structures, so these tests pin down the DAG
# shape independently of Snakemake and containers.
#
# Fixtures (tracked, read-only):
#   tests/evolverMammals/evolverMammals.txt                    - the input file
#   tests/evolverMammals/evolverMammals-out/evolverMammals.txt - real cactus-prepare
#                                                                output for that input
#############################################################################

import os

import lib.cactuslib as CACTUSLIB
import lib.treelib as TREELIB
from tests.helpers import MAMMALS_DIR

INPUT_FILE = os.path.join(MAMMALS_DIR, "evolverMammals.txt")
CACTUS_FILE = os.path.join(MAMMALS_DIR, "evolverMammals-out", "evolverMammals.txt")

TIP_OUTPUTS = ["simCow.chr6", "simDog.chr6", "simHuman.chr6", "simMouse.chr6", "simRat.chr6"]


def parse_mammals():
    # The same sequence of calls cactus.smk makes before its rules are defined
    tips = TREELIB.readTips(INPUT_FILE, False, 50)
    internals, anc_tree = TREELIB.initializeInternals(CACTUS_FILE, tips, False, 50)
    tinfo, anc_tree, root = TREELIB.treeParse(anc_tree)
    tips, internals = TREELIB.parseInternals(internals, tips, tinfo, anc_tree)
    internal_seq_ext = CACTUSLIB.normalizeInternalSeqs(internals)
    return tips, internals, tinfo[root][3], internal_seq_ext


def test_tips():
    tips, _, _, _ = parse_mammals()
    assert list(tips) == ["simCow_chr6", "simDog_chr6", "simHuman_chr6", "simMouse_chr6", "simRat_chr6"]
    # Inputs come from the input file as written; outputs are the basenames cactus-prepare assigned
    assert tips["simCow_chr6"]["input"] == ["evolverMammals-seq/simCow.chr6"]
    assert [tips[t]["output"] for t in tips] == TIP_OUTPUTS


def test_internal_nodes_and_root():
    _, internals, root_name, _ = parse_mammals()
    assert set(internals) == {"Anc0", "Anc1", "Anc2", "mr"}
    assert root_name == "Anc0"


def test_rounds_match_cactus_prepare_plan():
    # cactus-prepare's own plan for this input aligns Anc2 and mr in round 0, Anc1 in
    # round 1 and Anc0 in round 2 (from its "### Round N" sections)
    _, internals, _, _ = parse_mammals()
    assert {n: internals[n]["round"] for n in internals} == {"Anc2": 0, "mr": 0, "Anc1": 1, "Anc0": 2}


def test_input_seqs():
    # Each node's blast inputs: every tip's preprocessed sequence, plus the ancestral
    # sequences from the round before it
    _, internals, _, _ = parse_mammals()
    expected = {
        "Anc2": set(TIP_OUTPUTS),
        "mr": set(TIP_OUTPUTS),
        "Anc1": set(TIP_OUTPUTS) | {"Anc2.fa.gz", "mr.fa.gz"},
        "Anc0": set(TIP_OUTPUTS) | {"Anc1.fa.gz"},
    }
    assert {n: set(internals[n]["input-seqs"]) for n in internals} == expected


def test_internal_seq_files():
    # cactus-prepare (v3+) writes gzipped ancestral sequences; the convert rule's output
    # extension comes from this
    _, internals, _, internal_seq_ext = parse_mammals()
    assert internal_seq_ext == ".fa.gz"
    assert {n: internals[n]["seq-file"] for n in internals} == {n: n + ".fa.gz" for n in internals}
