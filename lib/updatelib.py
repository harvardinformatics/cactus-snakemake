#############################################################################
# Functions related to the update and replace cactus snakemake pipelines
# https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/updating-alignments.md
# https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/cactus-update-prepare.md
#
# Gregg Thomas, April 2025
#############################################################################

import os
import re
import subprocess
import logging

#############################################################################

cactuslib_logger = logging.getLogger('cactuslib')
# Get the logger for the cactuslib module

#############################################################################

def getGenomesToAddUpdate(input_file):

    #genome_names = [];
    #genome_exts  = [];
    # The list of genome names to add to the tree

    with open(input_file) as f:
        num_lines = sum(1 for line in open(input_file));
        if num_lines > 1:
            cactuslib_logger.warning(f"More than one genome specified in the input file. Only the genome on the first line will be used.");
        # If there is more than one genome in the input file, warn the user and only use the first one

        for line in open(input_file):
            if not line.strip():
                continue;
            # Skip any blank lines

            line = line.strip().split()
            # Split the line into a list

            #seq_file_ext = os.path.splitext(line[1])[1]

            #genome_names.append(line[0]);
            #genome_exts.append(seq_file_ext[1:]);
            # Add the genome name and extension to the lists

            genome_name = line[0];
            genome_ext = os.path.splitext(line[1])[1][1:];

            break;

    cactuslib_logger.info(f"Genomes to add: {genome_name}");
    # if cactuslib_logger.isEnabledFor(logging.DEBUG):
    #     for g in range(len(genome_names)):
    cactuslib_logger.debug(f"{genome_name}: {genome_ext}");
    cactuslib_logger.debug("===================================================================================");

    return genome_name, genome_ext;

#############################################################################

def getGenomesToAddReplace(seq_out_file, replace_id):
    with open(seq_out_file, "r") as f:
        first = True;
        for line in f:
            line = line.strip();
            if not line:
                continue;
            # Skip any blank lines

            if first:
                ancestor = re.findall(r'\)([^;]+);', line)[0];
                first = False;

            line = line.split("\t");
            if line[0] == replace_id:
                new_genome_file = line[1];

    return new_genome_file, ancestor;


#############################################################################

def runCactusUpdatePrepare(input_hal, input_file, cactus_path, output_dir, update_type, use_gpu, log_dir, dry_run, parent, child, new_anc_name, new_top_bl):
# This function runs cactus-update-prepare on the input file and saves the output in the output directory

    log_prefix = "cactus-update-prepare";
    # if dry_run:
        # output_dir = "/tmp/cactus-update-smk-dryrun/";
        # os.makedirs(output_dir, exist_ok=True);
        # log_prefix = os.path.join(output_dir, "cactus-update-prepare");
    # If this is a dry run, create a temporary output directory and log file

    if update_type not in ["branch", "replace"]:
        cactuslib_logger.error("Invalid update type. Must be 'branch' or 'replace'.");
        sys.exit(1);
    # Check the update type

    if not os.path.exists(input_hal):
        cactuslib_logger.error(f"Input hal file {input_hal} does not exist. Exiting.");
        sys.exit(1);
    # Check the input hal file

    if not parent:
        cactuslib_logger.error("Parent/replacement genome not specified. Exiting.");
        sys.exit(1);
    # Check the parent genome

    if update_type == "branch":
        command = cactus_path + ["cactus-update-prepare", 
                                    "add", 
                                    update_type, 
                                    input_hal, 
                                    input_file, 
                                    "--outDir", output_dir
                                    ];

        if update_type == "node":
            if child:
                cactuslib_logger.warning("Child genome specified for node update. This will be ignored.");
            # If a child genome is specified for a node update, ignore it
            command += ["--genome", parent];
        elif update_type == "branch":
            if not child:
                cactuslib_logger.error("Child genome not specified for branch update. Exiting.");
                sys.exit(1);
            # Check the child genome
            command += ["--parentGenome", parent, 
                        "--childGenome", child,
                        "--ancestorName", new_anc_name,
                        "--topBranchLength", new_top_bl,
                        ];
        # The command to run cactus-prepare
    # For branch updates, we need to specify the parent and child genomes as well as the new branch length above the new node

    elif update_type == "replace":
        command = cactus_path + ["cactus-update-prepare", 
                                    "replace", 
                                    input_hal, 
                                    input_file, 
                                    "--genome", parent, 
                                    "--outDir", output_dir
                                    ];
    # For replace updates, we only need to specify the parent genome, which is the one being replaced

    # if use_gpu:
    #     command.append("--gpu");
    # The command to run cactus-prepare

    cactuslib_logger.info(f"Command to run cactus-update-prepare: {' '.join(command)}");
    cactuslib_logger.debug("===================================================================================");
    # Debug output

    # if use_gpu:
    #     logfile = log_prefix + "-gpu.log";
    # else:
    logfile = log_prefix + ".log";
    # The log file name

    # if dry_run:
    #     logpath = logfile;
    # else:
    logpath = os.path.join(log_dir, logfile);
    # The log file path

    try:
        with open(logpath, "w") as log_file:
            subprocess.run(command, check=True, stdout=log_file, stderr=subprocess.STDOUT)
    except FileNotFoundError as e:
        cactuslib_logger.error(f"File not found: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        cactuslib_logger.error(f"Error running cactus-prepare: {e}");
        cactuslib_logger.debug(f"Command: {' '.join(command)}");
        cactuslib_logger.error(f"Check log file for more info: {logpath}");        
        sys.exit(1)
    # Run the command and check for errors

    cactuslib_logger.info(f"Successfully ran cactus-update-prepare. Parsing file names form {output_dir}/seq_file.out");

    with open(os.path.join(output_dir, "seq_file.out")) as f:
        seq_files = [];
        next(f)  # Skip the first line
        for line in f:
            if not line.strip():
                continue;
            # Skip any blank lines
            
            line = line.strip().split("\t");
            if line[0] not in [parent, new_anc_name]:
                seq_files.append(line[1]);
            # Add the seq files to the list if they are not the parent or new ancestor

    return seq_files;
    # Return the preprocess file paths

#############################################################################