#############################################################################
# Pipeline for running cactus for whole genome alignment
# See: https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/progressive.md#running-step-by-step
#
# Created April 2022
# Gregg Thomas
#############################################################################

import sys
import os
import re
import logging
import subprocess

import lib.cactuslib as CACTUSLIB
from lib.cactuslib import spacedOut as SO
import lib.treelib as TREELIB

from functools import partial

#############################################################################
# System setup

config_flag = config.get("display", False);
version_flag = config.get("version", False);
info_flag = config.get("info", False);
debug = config.get("debug", False);
prep_only = config.get("prep", False);
#debug = True;
# A hacky way to get some custom command line arguments for the pipeline
# These just control preprocessing flags that stop the pipeline early anyways

pad = config.get("pad", 50);
debug_pad = pad - 1;
# The padding for some of the log messages

MAIN, DRY_RUN, OUTPUT_DIR, LOG_DIR, TMPDIR, LOG_LEVEL, LOG_VERBOSITY, TOP_LEVEL_EXECUTOR = CACTUSLIB.pipelineSetup(config, sys.argv, version_flag, info_flag, config_flag, debug, workflow, pad);
# Setup the pipeline, including the output directory, log directory, and tmp directory

CLOG = logging.getLogger('cactuslib')
# Setup logging if debugging

getRuleResources = partial(CACTUSLIB.getResources, config, TOP_LEVEL_EXECUTOR)
# This maps the function to get rule resources from the config file
# so we don't have to pass config each time we call it

#############################################################################
# Cactus setup

USE_GPU = config["use_gpu"]
# Whether to use GPU or CPU cactus

CACTUS_PATH, CACTUS_PATH_TMP, VERSION_TAG = CACTUSLIB.parseCactusPath(config["cactus_path"], USE_GPU, MAIN, TMPDIR, pad);
# Parse the cactus path from the config file

KEG_PATCH_FILE = None
if USE_GPU:
    KEG_PATCH_FILE = CACTUSLIB.downloadKegPatch(OUTPUT_DIR, MAIN, VERSION_TAG)
# Download the KEG patch file if using GPU cactus, and set the path to it

#############################################################################
# Input files and output paths

INPUT_FILE = os.path.abspath(config["input_file"]);
if not os.path.isfile(INPUT_FILE):
    CLOG.error(f"Could not find input file at {INPUT_FILE}");
    sys.exit(1);
else:
    if MAIN:
        CLOG.info(f"Input file found at {INPUT_FILE}");
# The cactus input file used to generate the config file with cactus-prepare

MAF_REFERENCE = config["maf_reference"];

OUTPUT_HAL = os.path.join(OUTPUT_DIR, f"{config['final_prefix']}.hal");
OUTPUT_MAF = os.path.join(OUTPUT_DIR, f"{config['final_prefix']}.{MAF_REFERENCE}.maf.gz");
OUTPUT_MAF_NODUPES = os.path.join(OUTPUT_DIR, f"{config['final_prefix']}.{MAF_REFERENCE}.nodupes.maf.gz");

if MAIN:
    CLOG.info(SO(f"Output HAL file will be at", pad) + f"{OUTPUT_HAL}");
    CLOG.info(SO(f"Reference genome for MAF file will be", pad) + f"{MAF_REFERENCE}");
    CLOG.info(SO(f"Output MAF file will be at", pad) + f"{OUTPUT_MAF}");
# The final output files for the pipeline

#job_path = os.path.join(OUTPUT_DIR, "jobstore");
# The temporary/job directory specified in cactus-prepare

#############################################################################
# cactus-prepare

if MAIN:
    CACTUSLIB.runCactusPrepare(INPUT_FILE, CACTUS_PATH, OUTPUT_DIR, OUTPUT_HAL, USE_GPU, LOG_DIR, DRY_RUN);
# if DRY_RUN:
#     CACTUS_FILE = os.path.join("/tmp/", "cactus-smk-dryrun", os.path.basename(INPUT_FILE));
#else:
CACTUS_FILE = os.path.join(OUTPUT_DIR, os.path.basename(INPUT_FILE));
# Run cactus-prepare to generate the cactus input file with ancestral nodes and labeled tree

#############################################################################
# Reading files

tips = TREELIB.readTips(INPUT_FILE, MAIN, pad);
# The main dictionary for storing information and file paths for tips in the tree:
# [genome name] : { 'input' : "original genome fasta file", 'name' : "genome name in tree (same as key)", 'output' : "expected output from preprocess step" }

####################

internals, anc_tree = TREELIB.initializeInternals(CACTUS_FILE, tips, MAIN, pad);
# The main dictionary for storing information and file paths for internal nodes in the tree:
# [node name] : { 'name' : "node name in tree", 'blast-inputs' : [the expected inputs for the blast step], 'align-inputs' : [the expected inputs for the align step],
#                   'hal-inputs' : [the expected inputs for the hal2fasta step], 'blast-output' : "the .paf file output from the blast step",
#                   'align-output' : "the .hal file output from the align step", 'hal-output' : "the fasta file output from the hal2fasta step" }

####################

tinfo, anc_tree, root = TREELIB.treeParse(anc_tree);
ROOT_NAME = tinfo[root][3];
tips, internals = TREELIB.parseInternals(internals, tips, tinfo, anc_tree);
# The tree is parsed to get the root node and the internal nodes are updated with the correct names

# for name in tips:
#     print(name);
#     print(tips[name]);

preprocess_out = [ tips[name]['output'] for name in tips ];
CLOG.debug(f"Preprocess output files: {preprocess_out}");
# The expected output from the preprocess step for each genome

if LOG_LEVEL == "debug":
    CLOG.debug("EXITING BEFORE RULES. DEBUG MODE.");
    sys.exit(0);
# Exit before running rules if in debug mode

if prep_only:
    CLOG.info("PREP ONLY FLAG SET. EXITING.");
    sys.exit(0);
# Exit before running rules if prep only flag is set

#############################################################################
# Final rule - rule that depends on final expected output file and initiates all
# the other rules

localrules: all

rule all:
    input:
        final_maf = OUTPUT_MAF,
        final_maf_nodupes = OUTPUT_MAF_NODUPES
        # The .maf file from rul maf
## Rule all specifies the final output files expected

# #############################################################################
# # Pipeline rules

def getPreprocessInputs(wildcards, key):
    preprocess_input = [ tips[name][key] for name in tips if tips[name]['output'] == wildcards.final_tip ];
    if not preprocess_input:
        return "dryrun_input";
    return preprocess_input[0];
# This function gets the input for the preprocess step for a given genome
# Avoids the IndexErrors with dummy wildcards that snakmake apparently uses sometimes??

rule preprocess:
    input:
        lambda wildcards: getPreprocessInputs(wildcards, 'input')
        #lambda wildcards: [ tips[name]['input'] for name in tips if tips[name]['output'] == wildcards.final_tip ][0]
    output:
        os.path.join(OUTPUT_DIR, "{final_tip}")    
    params:
        path = CACTUS_PATH_TMP,
        input_file = INPUT_FILE,
        cactus_file = os.path.join(OUTPUT_DIR, CACTUS_FILE),
        genome_name = lambda wildcards: [ name for name in tips if tips[name]['output'] == wildcards.final_tip ][0],
        host_tmp_dir = lambda wildcards: os.path.join(TMPDIR, [ name for name in tips if tips[name]['output'] == wildcards.final_tip ][0] + "-preprocess"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        job_tmp_dir = lambda wildcards: os.path.join("/tmp", [ name for name in tips if tips[name]['output'] == wildcards.final_tip ][0] + "-preprocess"), # This is the tmp dir in the container, which is bound to the host tmp dir
        # gpu_opt = f"--gpu {config["preprocess_gpu"]}" if USE_GPU else "",
        rule_name = "preprocess"
    log:
        job_log = os.path.join(LOG_DIR, "{final_tip}.preprocess.log")
    resources:
        **getRuleResources("preprocess")
    run:
        cmd = params.path + [
            "cactus-preprocess",
            params.job_tmp_dir,
            params.input_file,
            params.cactus_file,
            "--inputNames", params.genome_name,
            "--logInfo",
            "--retryCount", "0",
            "--maxCores", str(resources.cpus_per_task)
        ];

        CACTUSLIB.runCommand(cmd, params.host_tmp_dir, log.job_log, params.rule_name, wildcards.final_tip)
        # When not requesting all CPU on a node: toil.batchSystems.abstractBatchSystem.InsufficientSystemResources: The job LastzRepeatMaskJob is requesting 64.0 cores, more than the maximum of 32 cores that SingleMachineBatchSystem was configured with, or enforced by --maxCores.Scale is set to 1.0.
## This rule runs cactus-preprocess for every genome (tip in the tree), which does some masking
## Runtimes for turtles range from 8 to 15 minutes with the above resoureces

####################

rule blast:
    input:
        lambda wildcards: [ os.path.join(OUTPUT_DIR, input_file) for input_file in internals[wildcards.internal_node]['input-seqs'] ]
    output:
        paf_file = os.path.join(OUTPUT_DIR, "{internal_node}.paf")
    params:
        path = CACTUS_PATH_TMP,
        cactus_file = os.path.join(OUTPUT_DIR, CACTUS_FILE),
        node = lambda wildcards: wildcards.internal_node,
        host_tmp_dir = lambda wildcards: os.path.join(TMPDIR, wildcards.internal_node + "-blast"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        job_tmp_dir = lambda wildcards: os.path.join("/tmp", wildcards.internal_node + "-blast"), # This is the tmp dir in the container, which is bound to the host tmp dir
        gpu_opt = USE_GPU,
        gpu_num = config['rule_resources']['blast']['gpus'],
        rule_name = "blast"
    log:
        job_log = os.path.join(LOG_DIR, "{internal_node}.blast.log")
    resources:
        **getRuleResources("blast"),
        slurm_extra = f"'--gres=gpu:{config['rule_resources']['blast']['gpus']}'" if USE_GPU else ""
    run:
        cmd = params.path + [
            "cactus-blast",
            params.job_tmp_dir,
            params.cactus_file,
            output.paf_file,
            "--root", params.node,
            "--logInfo",
            "--retryCount", "0",
            "--lastzCores", str(resources.cpus_per_task)
        ];

        if params.gpu_opt:
            cmd += ["--gpu", str(params.gpu_num)];

        CACTUSLIB.runCommand(cmd, params.host_tmp_dir, log.job_log, params.rule_name, wildcards.internal_node)
## This rule runs cactus-blast for every internal node
## Runtimes for turtles range from 1 to 10 hours with the above resources

####################

rule align:
    input:
        paf_file = os.path.join(OUTPUT_DIR, "{internal_node}.paf"),
        #seq_files = lambda wildcards: [ os.path.join(OUTPUT_DIR, input_file) for input_file in internals[wildcards.internal_node]['desc-seqs'] ]
    output:
        hal_file = os.path.join(OUTPUT_DIR, "{internal_node}.hal")
    params:
        path = CACTUS_PATH_TMP,
        #config_file = os.path.join(OUTPUT_DIR, CONFIG_FILE),
        cactus_file = os.path.join(OUTPUT_DIR, CACTUS_FILE),
        node = lambda wildcards: wildcards.internal_node,
        keg_patch_file = KEG_PATCH_FILE,
        #job_dir = lambda wildcards: os.path.join(TMPDIR, wildcards.internal_node + "-align"),
        host_tmp_dir = lambda wildcards: os.path.join(TMPDIR, wildcards.internal_node + "-align"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        job_tmp_dir = lambda wildcards: os.path.join("/tmp", wildcards.internal_node + "-align"), # This is the tmp dir in the container, which is bound to the host tmp dir
        work_dir = TMPDIR,
        # gpu_opt = "--gpu" if USE_GPU else "",
        rule_name = "align"
    log:
        job_log = os.path.join(LOG_DIR, "{internal_node}.align.log")
    resources:
        **getRuleResources("align")
    run:
        cmd = params.path + [
            "cactus-align",
            params.job_tmp_dir,
            params.cactus_file,
            input.paf_file,
            output.hal_file,
            "--root", params.node,
            "--logInfo",
            "--retryCount", "0",
            #"--workDir", params.work_dir,
            "--maxCores", str(resources.cpus_per_task),
            #"--defaultDisk", "450G"
        ];

        if params.keg_patch_file:
            cmd += ["--configFile", params.keg_patch_file];

        CACTUSLIB.runCommand(cmd, params.host_tmp_dir, log.job_log, params.rule_name, wildcards.internal_node)
## This rule runs cactus-align for every internal node
## Runtimes for turtles range from 4 to 16 hours with the above resources

####################

rule convert:
    input:
        hal_file = os.path.join(OUTPUT_DIR, "{internal_node}.hal")
        #lambda wildcards: [ os.path.join(output_dir, input_file) for input_file in internals[wildcards.internal_node]['hal-inputs'] ][0]
    output:
        fa_file = os.path.join(OUTPUT_DIR, "{internal_node}.fa")
    params:
        path = CACTUS_PATH,
        node = lambda wildcards: wildcards.internal_node,
        rule_name = "convert"
    log:
        job_log = os.path.join(LOG_DIR, "{internal_node}.convert.log")
    resources:
        **getRuleResources("convert")
    run:
        cmd = params.path + [
            "hal2fasta",
            input.hal_file,
            params.node,
            "--outFaPath", output.fa_file,
            "--hdf5InMemory"
        ];

        CACTUSLIB.runCommand(cmd, None, log.job_log, params.rule_name, params.node)
## This rule runs hal2fasta to convert .hal files for each internal node to .fasta files
## Runtime for turtles is only about 30 seconds per node

####################

rule copy_hal:
    input:
        all_hals = expand(os.path.join(OUTPUT_DIR, "{internal_node}.fa"), internal_node=internals),
        anc_hal = os.path.join(OUTPUT_DIR, ROOT_NAME + ".hal")
    output:
        final_hal = OUTPUT_HAL
    params:
        rule_name = "copy_hal"
    log:
        job_log = os.path.join(LOG_DIR, "copy-hal.log")
    resources:
        **getRuleResources("copy_hal") 
    run:
        cmd = ["cp", input.anc_hal, output.final_hal];

        CACTUSLIB.runCommand(cmd, None, log.job_log, params.rule_name)
## Copying the root .hal file here, since failures in the subsequent rules
## would mean the blast/align steps have to be re-run for that node, but this means a little extra
## storage is required

####################

rule append:
    input:
        final_hal = OUTPUT_HAL
    output:
        append_done = touch(os.path.join(LOG_DIR, "hal-append-subtree.done"))
    params:
        path = CACTUS_PATH_TMP,
        job_tmp_dir = os.path.join(TMPDIR, "append-hal"),
        rule_name = "append"
    log:
        job_log = os.path.join(LOG_DIR, "hal-append-subtree.log")
    resources:
        **getRuleResources("append")
    run:
        node_count = 1;
        for node in internals:
            if node == ROOT_NAME:
                continue;
            # If the node is the root we don't want to append since that is the hal file we
            # are appending to

            node_hal = os.path.join(OUTPUT_DIR, node + ".hal");

            cmd = params.path + [
                "halAppendSubtree",
                OUTPUT_HAL,
                node_hal,
                node,
                node,
                "--merge",
                "--hdf5InMemory"
            ];

            if node_count == 1:
                file_mode = "w+";
            else:
                file_mode = "a+";

            CACTUSLIB.runCommand(cmd, params.job_tmp_dir, log.job_log, params.rule_name, node, fmode=file_mode);
            # Generate the command for the current node

            node_count += 1;
            # Increment the node count
        ## End node loop
    ## This rule runs halAppendSubtree on every internal node in the tree to combine alignments into a single file.
    ## Because this command writes to the same file for every node, jobs must be run serially.
####################

rule maf:
    input:
        final_hal = OUTPUT_HAL,
        append_done = os.path.join(LOG_DIR, "hal-append-subtree.done")
    output:
        final_maf = OUTPUT_MAF,
        final_maf_nodupes = OUTPUT_MAF_NODUPES
    params:
        path = CACTUS_PATH_TMP,
        ref_genome = MAF_REFERENCE,
        chunk_size = 500000, # 500kb
        host_tmp_dir = os.path.join(TMPDIR, "maf"),
        job_tmp_dir = os.path.join("/tmp", "maf"),
        rule_name = "maf"
    log:
        job_log = os.path.join(LOG_DIR, "maf.log")
    resources:
        **getRuleResources("maf")
    run:
        cmd = params.path + [
            "cactus-hal2maf",
            params.job_tmp_dir,
            input.final_hal,
            output.final_maf,
            "--refGenome", params.ref_genome,
            "--chunkSize", str(params.chunk_size),
            "--batchCount", str(resources.cpus_per_task),
            "--filterGapCausingDupes"
        ];

        CACTUSLIB.runCommand(cmd, params.host_tmp_dir, log.job_log, params.rule_name);

        cmd = params.path + [
            "cactus-hal2maf",
            params.job_tmp_dir,
            input.final_hal,
            output.final_maf_nodupes,
            "--refGenome", params.ref_genome,
            "--chunkSize", str(params.chunk_size),
            "--batchCount", str(resources.cpus_per_task),
            "--filterGapCausingDupes",
            "--dupeMode", "single"
        ];

        CACTUSLIB.runCommand(cmd, params.host_tmp_dir, log.job_log, params.rule_name, fmode="a+");

#############################################################################
