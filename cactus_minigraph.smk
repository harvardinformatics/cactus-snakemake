#############################################################################
# Pipeline for running cactus-minigraph for pangenome creation
# See: https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/pangenome.md
#
# Created March 2025
# Gregg Thomas
#############################################################################

import sys
import os
import re
import logging
import subprocess

import lib.cactuslib as CACTUSLIB
from lib.cactuslib import spacedOut as SO

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

pad = config.get("pad", 40);
debug_pad = pad - 1;
# The padding for some of the log messages

MAIN, DRY_RUN, OUTPUT_DIR, LOG_DIR, TMPDIR, LOG_LEVEL, LOG_VERBOSITY, TOP_LEVEL_EXECUTOR = CACTUSLIB.pipelineSetup(config, sys.argv, version_flag, info_flag, config_flag, debug, workflow, pad);
# Setup the pipeline, including the output directory, log directory, and tmp directory

CLOG = logging.getLogger('cactuslib')
# Setup logging if debugging

getRuleResources = partial(CACTUSLIB.getResources, config, TOP_LEVEL_EXECUTOR);
# This maps the function to get rule resources from the config file
# so we don't have to pass config each time we call it

#############################################################################
# Cactus setup

CACTUS_PATH, CACTUS_PATH_TMP, VERSION_TAG = CACTUSLIB.parseCactusPath(config["cactus_path"], False, MAIN, TMPDIR, pad);
# Parse the cactus path from the config file

#############################################################################
# Input files and output paths

INPUT_FILE_ORIG = os.path.abspath(config["input_file"]);
if not os.path.isfile(INPUT_FILE_ORIG):
    CLOG.error(f"Could not find input file at {INPUT_FILE_ORIG}");
    sys.exit(1);
else:
    if MAIN:
        CLOG.info(SO(f"Input file found at", pad) +  f"{INPUT_FILE_ORIG}");
# The cactus input file used to generate the config file with cactus-prepare

INPUT_FILE_COPY = os.path.join(OUTPUT_DIR, os.path.basename(INPUT_FILE_ORIG));
COPY_READY_FILE = os.path.join(OUTPUT_DIR, "copy_input.done");
if MAIN:
    CLOG.info(f"During rule copy_input, a copy of the input file will be created and modified at {INPUT_FILE_COPY}");
# A copy of the input file must be created and used since cactus-minigraph modifies the input file

CHROMS_DIR = os.path.join(OUTPUT_DIR, "chroms");
# The directory where the split chromosomes are stored
# (generated during split:)

CHROMS_FILE = os.path.join(CHROMS_DIR, "chromfile.txt");
# The file that contains the list of chromosomes and their corresponding sequence files
# (generated during split:)

CHROMS_SEQFILE_DIR = os.path.join(CHROMS_DIR, "seqfiles");
# The directory where the split chromosome sequence files are stored
# (generated during split:)

ALIGN_DIR = os.path.join(OUTPUT_DIR, "chrom-alignments");
# The directory where the aligned chromosomes are stored
# (generated during align:)

FINAL_DIR = os.path.join(OUTPUT_DIR, "final");
# The directory where the final output files are stored
# (generated during join:)

REF_GENOME = config["reference"];
# The reference genome used for alignment

PREFIX = config["prefix"];
# The prefix for the output files

#OUTPUT_HAL = os.path.join(OUTPUT_DIR, config["final_hal"]);
#OUTPUT_MAF = os.path.join(OUTPUT_DIR, config["final_hal"].replace(".hal", ".maf"));

#job_path = os.path.join(OUTPUT_DIR, "jobstore");
# The temporary/job directory specified in cactus-prepare

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
        final_hal = os.path.join(FINAL_DIR, f"{PREFIX}.full.hal"),
        final_gfa = os.path.join(FINAL_DIR, f"{PREFIX}.gfa.gz"),
        final_vcf = os.path.join(FINAL_DIR, f"{PREFIX}.vcf.gz"),
        final_vcf_index = os.path.join(FINAL_DIR, f"{PREFIX}.vcf.gz.tbi"),
        final_dist = os.path.join(FINAL_DIR, f"{PREFIX}.dist"),
        final_gbz = os.path.join(FINAL_DIR, f"{PREFIX}.gbz"),
        final_min = os.path.join(FINAL_DIR, f"{PREFIX}.min"),
        final_raw_vcf = os.path.join(FINAL_DIR, f"{PREFIX}.raw.vcf.gz"),
        final_raw_vcf_index = os.path.join(FINAL_DIR, f"{PREFIX}.raw.vcf.gz.tbi"),
        final_stats = os.path.join(FINAL_DIR, f"{PREFIX}.stats.tgz")
        #expand(os.path.join(OUTPUT_DIR, "chrom-alignments", "{chrom}.hal"), chrom=gather_chromosomes)
        #getAlignIO(os.path.join(OUTPUT_DIR, "chroms", "chromfile.txt"), "chrom-alignments")["hals"]
        #directory(os.path.join(OUTPUT_DIR, "chroms")),
        #os.path.join(OUTPUT_DIR, "chroms", "chromfile.txt")
## Rule all specifies the final output files expected

# #############################################################################
# # Pipeline rules

rule copy_input:
    input:
        cactus_input = INPUT_FILE_ORIG
    output:
        ready_file = touch(COPY_READY_FILE)
    params:
        cactus_input_copy = INPUT_FILE_COPY,
        fasta = os.path.join(OUTPUT_DIR, f"{PREFIX}.sv.gfa.fa")
    resources:
        **getRuleResources("copy_input")
    run:
        # Define the new base directory
        new_base_dir = os.path.dirname(input.cactus_input);

        # Read the input file
        with open(input.cactus_input, "r") as infile:
            lines = infile.readlines();
        
        #labels = [];
        #outlines = [];

        # Write to the output file
        with open(params.cactus_input_copy, "w") as outfile:
            for line in lines:
                label, path = line.strip().split("\t");
                
                # Determine if the path is a URL or absolute
                if not (path.startswith("http://") or path.startswith("https://") or os.path.isabs(path)):
                    # It's a relative path, update it
                    path = os.path.normpath(os.path.join(new_base_dir, path));
                
                # Write the updated line to the output file
                outfile.write(f"{label}\t{path}\n");

                #labels.append(label);
                #outlines.append(f"{label}\t{path}\n");
            #star_tree = "(" + "".join([ f"{label}:1.0," for label in labels ]) + "_MINIGRAPH_:1);\n";
            #outfile.write(star_tree);
            #for outline in outlines:
            #    outfile.write(outline);
            #outfile.write(f"_MINIGRAPH_\tfile://{params.fasta}\n");
            # The commented lines here are used if we want to actually re-write the input file before cactus-minigraph, 
            # but cactus-minigraph does this regardless, so it doesn't really matter
# This is necessary because cactus-minigraph modifies the input file, which means if we used the original, snakemake would think 
# it always needs to re-run the whole pipeline. This rule makes a copy of the input file and updates the paths to be absolute.

####################

rule minigraph:
    input:
        ready_file = COPY_READY_FILE
    output:
        sv_gfa = os.path.join(OUTPUT_DIR, f"{PREFIX}.sv.gfa"),
    params:
        path = CACTUS_PATH,
        cactus_input = INPUT_FILE_COPY,
        ref_genome = REF_GENOME,
        job_tmp_dir = os.path.join(TMPDIR, "minigraph"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        rule_name = "minigraph"
    log:
        job_log = os.path.join(LOG_DIR, f"{PREFIX}.minigraph.log")
    resources:
        **getRuleResources("minigraph")
    run:
        cmd = params.path + [
            "cactus-minigraph",
            params.job_tmp_dir,
            params.cactus_input,
            output.sv_gfa,
            "--reference", params.ref_genome
        ];
        CACTUSLIB.runCommand(cmd, params.job_tmp_dir, log.job_log, params.rule_name);
    # shell:
    #     """
    #     {params.path} cactus-minigraph {params.job_tmp_dir} {input.cactus_input} {output.sv_gfa} --reference {params.ref_genome} --restart
    #     """
    # Keeping shell around now for debugging purposes

####################

rule graphmap:
    input:
        sv_gfa = os.path.join(OUTPUT_DIR, f"{PREFIX}.sv.gfa")
    output:
        paf = os.path.join(OUTPUT_DIR, f"{PREFIX}.paf"),
        fasta = os.path.join(OUTPUT_DIR, f"{PREFIX}.sv.gfa.fa"),
        gaf = os.path.join(OUTPUT_DIR, f"{PREFIX}.gaf.gz"),
        paf_filter_log = os.path.join(OUTPUT_DIR, f"{PREFIX}.paf.filter.log"),
        paf_unfiltered = os.path.join(OUTPUT_DIR, f"{PREFIX}.paf.unfiltered.gz")
    params:
        path = CACTUS_PATH,
        cactus_input = INPUT_FILE_COPY,
        ref_genome = REF_GENOME,
        job_tmp_dir = os.path.join(TMPDIR, "graphmap"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        rule_name = "graphmap"
    log:
        job_log = os.path.join(LOG_DIR, f"{PREFIX}.graphmap.log")
    resources:
        **getRuleResources("graphmap")
    run:
        cmd = params.path + [
            "cactus-graphmap",
            params.job_tmp_dir,
            params.cactus_input,
            input.sv_gfa,
            output.paf,
            "--outputFasta", output.fasta,
            "--reference", params.ref_genome
        ];
        CACTUSLIB.runCommand(cmd, params.job_tmp_dir, log.job_log, params.rule_name);

####################

checkpoint split:
    input:
        sv_gfa = os.path.join(OUTPUT_DIR, f"{PREFIX}.sv.gfa"),
        paf = os.path.join(OUTPUT_DIR, f"{PREFIX}.paf")
    output:
        # chroms_dir = directory(CHROMS_DIR),
        # seq_dir = directory(CHROMS_SEQFILE_DIR),
        chroms_file = CHROMS_FILE,
        contig_sizes = os.path.join(CHROMS_DIR, "contig_sizes.tsv"),
        minigraph_split_log = os.path.join(CHROMS_DIR, "minigraph.split.log")
    params:
        path = CACTUS_PATH,
        cactus_input = INPUT_FILE_COPY,
        ref_genome = REF_GENOME,
        chroms_dir = CHROMS_DIR,
        job_tmp_dir = os.path.join(TMPDIR, "split"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        rule_name = "split"
    log:
        job_log = os.path.join(LOG_DIR, f"{PREFIX}.split.log")
    resources:
        **getRuleResources("split")
    run:
        cmd = params.path + [
            "cactus-graphmap-split",
            params.job_tmp_dir,
            params.cactus_input,
            input.sv_gfa,
            input.paf,
            "--outDir", params.chroms_dir,
            "--reference", params.ref_genome
        ];
        CACTUSLIB.runCommand(cmd, params.job_tmp_dir, log.job_log, params.rule_name);

####################

rule align:
    input:
        chrom_seqfile = os.path.join(CHROMS_SEQFILE_DIR, "{chrom}.seqfile"),
        chrom_paf = os.path.join(CHROMS_DIR, "{chrom}", "{chrom}.paf")
    output:
        chrom_hal = os.path.join(ALIGN_DIR, "{chrom}.hal"),
        chrom_vg = os.path.join(ALIGN_DIR, "{chrom}.vg")
    params:
        path = CACTUS_PATH,
        ref_genome = REF_GENOME,
        job_tmp_dir = os.path.join(TMPDIR, "align-{chrom}"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        rule_name = "align"
    log:
        job_log = os.path.join(LOG_DIR, f"{PREFIX}.align.{{chrom}}.log")
    resources:
        **getRuleResources("align")
    run:
        cmd = params.path + [
            "cactus-align",
            params.job_tmp_dir,
            input.chrom_seqfile,
            input.chrom_paf,
            output.chrom_hal,
            "--pangenome",
            "--reference", params.ref_genome,
            "--outVG"
        ];

        # if params.gpu_opt:
        #     cmd.append("--gpu");

        CACTUSLIB.runCommand(cmd, params.job_tmp_dir, log.job_log, params.rule_name, wildcards.chrom);

####################

def gatherChromosomes(wildcards):
# This makes sure the chromosomes file is generated 
# from a checkpoint (split) and reads it in for use in the join and align rules

    chroms_file = checkpoints.split.get(**wildcards).output.chroms_file;
    # 'checkpoints.split.get(...)' ensures the file is generated.

    with open(chroms_file) as f:
        chroms = [line.strip().split("\t")[0] for line in f if line.strip()];
    # Read in the chromosomes file

    return chroms;

####################

rule join:
    input:
        chrom_hal = expand(os.path.join(ALIGN_DIR, "{chrom}.hal"), chrom=gatherChromosomes),
        chrom_vg = expand(os.path.join(ALIGN_DIR, "{chrom}.vg"), chrom=gatherChromosomes)
    output:
        final_hal = os.path.join(FINAL_DIR, f"{PREFIX}.full.hal"),
        final_gfa = os.path.join(FINAL_DIR, f"{PREFIX}.gfa.gz"),
        final_vcf = os.path.join(FINAL_DIR, f"{PREFIX}.vcf.gz"),
        final_vcf_index = os.path.join(FINAL_DIR, f"{PREFIX}.vcf.gz.tbi"),
        final_dist = os.path.join(FINAL_DIR, f"{PREFIX}.dist"),
        final_gbz = os.path.join(FINAL_DIR, f"{PREFIX}.gbz"),
        final_min = os.path.join(FINAL_DIR, f"{PREFIX}.min"),
        final_raw_vcf = os.path.join(FINAL_DIR, f"{PREFIX}.raw.vcf.gz"),
        final_raw_vcf_index = os.path.join(FINAL_DIR, f"{PREFIX}.raw.vcf.gz.tbi"),
        final_stats = os.path.join(FINAL_DIR, f"{PREFIX}.stats.tgz")
    params:
        path = CACTUS_PATH_TMP,
        ref_genome = REF_GENOME,
        chrom_haldir = ALIGN_DIR,
        join_outdir = FINAL_DIR,
        prefix = PREFIX,
        host_tmp_dir = os.path.join(TMPDIR, "join"), # This is the tmp dir for the host system, which is bound to /tmp in the singularity container
        job_tmp_dir = os.path.join("/tmp/", "join"), # This is the tmp dir for the singularity container
        rule_name = "join"
    log:
        job_log = os.path.join(LOG_DIR, f"{PREFIX}.join.log")
    resources:
        **getRuleResources("join")
    run:
        vg_files = [
            os.path.join(params.chrom_haldir, f) for f in os.listdir(params.chrom_haldir)
            if f.endswith('.vg')
        ]

        hal_files = [
            os.path.join(params.chrom_haldir, f) for f in os.listdir(params.chrom_haldir)
            if f.endswith('.hal')
        ]
        # Need to manually expand the vg and hal files since subprocess.run() won't do it later on

        cmd = params.path + [
            "cactus-graphmap-join",
            params.job_tmp_dir,
            "--vg"
        ] + vg_files + [
            "--hal"
        ] + hal_files + [
            "--outDir", params.join_outdir,
            "--outName", params.prefix,
            "--reference", params.ref_genome,
            "--vcf",
            "--giraffe", "clip"
        ];
        CACTUSLIB.runCommand(cmd, params.host_tmp_dir, log.job_log, params.rule_name);

#############################################################################