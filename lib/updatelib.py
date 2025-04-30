#############################################################################
# Functions related to the update and replace cactus snakemake pipelines
# https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/updating-alignments.md
# https://github.com/ComparativeGenomicsToolkit/cactus/blob/master/doc/cactus-update-prepare.md
#
# Gregg Thomas, April 2025
#############################################################################

import os
import re
import math
import subprocess
import logging

from lib.cactuslib import spacedOut as SO

#############################################################################

CLOG = logging.getLogger('cactuslib')
# Get the logger for the cactuslib module

#############################################################################

def createUpdateInputFile(cactus_update_file, genome_name, genome_fasta, new_bl, output_dir, pad):
# This function creates the input file for cactus-update-prepare

    if not os.path.isfile(genome_fasta):
        CLOG.error(f"Genome fasta file {genome_fasta} does not exist. Exiting.");
        sys.exit(1);
    # Check the genome fasta file
    genome_fasta = os.path.abspath(genome_fasta);
    # Get the absolute path of the genome fasta file

    if new_bl:
        new_bl = str(new_bl);
    else:
        new_bl = "1.0";
    # If no branch length is specified, set it to an empty string

    with open(cactus_update_file, "w") as f:
        f.write(f"{genome_name}\t{genome_fasta}\t{new_bl}\n");
        # Write the genome name and fasta file to the input file

    CLOG.info(SO(f"Created cactus-update-prepare input file", pad) + f"{cactus_update_file}");
    # The input file for cactus-update-prepare

#############################################################################

def createReplaceInputFile(cactus_replace_file, genome_name, genome_fasta, output_dir, pad):
# This function creates the input file for cactus-update-prepare

    if not os.path.isfile(genome_fasta):
        CLOG.error(f"Genome fasta file {genome_fasta} does not exist. Exiting.");
        sys.exit(1);
    # Check the genome fasta file
    genome_fasta = os.path.abspath(genome_fasta);

    with open(cactus_replace_file, "w") as f:
        f.write(f"{genome_name}\t{genome_fasta}\n");
        # Write the genome name and fasta file to the input file

    CLOG.info(SO(f"Created cactus-update-prepare input file", pad) + f"{cactus_replace_file}");
    # The input file for cactus-update-prepare

#############################################################################

def createAddOutgroupInputFiles(file_dict, pre_file, post_file, output_dir, pad):
# This function creates the input file for cactus-update-prepare

    if not os.path.isfile(file_dict["new-genome"]["fasta-orig"]):
        CLOG.error(f"Genome fasta file {file_dict['new-genome']['fasta-orig']} does not exist. Exiting.");
        sys.exit(1);
    # Check the genome fasta file
    
    genome_name = file_dict["new-genome"]["name"];
    genome_bl = file_dict["new-genome"]["branch-length"];
    old_root_name = file_dict["old-root"]["name"];
    old_root_bl = file_dict["old-root"]["branch-length"];
    new_root_name = file_dict["new-root"]["name"];
    # Unpack the file_dict dictionary

    with open(pre_file, "w") as f:
        pre_tree = f"({old_root_name}:{old_root_bl},{genome_name}:{genome_bl});"
        f.write(f"{pre_tree}\n");
        # Write the pre-update tree to the input file

        for node in file_dict:
            if node == "new-root":
                continue;
            # Skip the new genome

            if node == "new-genome":
                file_dict[node]["fasta"] = file_dict["new-genome"]["fasta-orig"];
            # If the node is the new genome, use the original fasta file

            f.write(f"{file_dict[node]['name']}\t{file_dict[node]['fasta']}\n");
            # Write the genome name and fasta file to the input file
    CLOG.info(SO(f"Created pre-input file", pad) + f"{pre_file}");
    # Write the pre-update tree and the genome names and fasta files to the input file

    with open(post_file, "w") as f:
        post_tree = f"({old_root_name}:{old_root_bl},{genome_name}:{genome_bl}){new_root_name};"
        f.write(f"{post_tree}\n");
        # Write the post-update tree to the input file

        for node in file_dict:
            if node == "new-genome":
                file_dict[node]["fasta"] = file_dict["new-genome"]["fasta-preprocess"];
            # If the node is the new genome, set the expected preprocessed fasta file

            f.write(f"{file_dict[node]['name']}\t{file_dict[node]['fasta']}\n");
            # Write the genome name and fasta file to the input file
    CLOG.info(SO(f"Created post-input file", pad) + f"{post_file}");

#############################################################################

def getOrigBranchLength(seq_out_file, child_node, new_anc_node, new_top_bl):

    with open(seq_out_file, "r") as f:
        tree = f.readline().strip();
    # Get the tree from the first line of the seq_file.out file

    pattern = r'(\w+):([\d.]+)';
    matches = re.findall(pattern, tree);
    node_lengths = {node: float(length) for node, length in matches};
    # A minimal tree parser

    orig_bl = node_lengths.get(child_node, 0) + node_lengths.get(new_anc_node, 0);
    # Get the original branch length of the child node and the new ancestor node

    new_bottom_bl = node_lengths.get(child_node, 0);

    if not math.isclose(orig_bl - new_top_bl, new_bottom_bl, rel_tol=1e-9):
        CLOG.error(f"Check branch lengths: orig {orig_bl}, top {new_top_bl}, bottom {new_bottom_bl}");
        sys.exit(1);
        # If the original branch length does not match the new branch length, exit

    return orig_bl;

#############################################################################

def getGenomesToAddUpdate(input_file):

    #genome_names = [];
    #genome_exts  = [];
    # The list of genome names to add to the tree

    with open(input_file) as f:
        num_lines = sum(1 for line in open(input_file));
        if num_lines > 1:
            CLOG.warning(f"More than one genome specified in the input file. Only the genome on the first line will be used.");
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

    CLOG.info(f"Genomes to add: {genome_name}");
    # if CLOG.isEnabledFor(logging.DEBUG):
    #     for g in range(len(genome_names)):
    CLOG.debug(f"{genome_name}: {genome_ext}");
    CLOG.debug("===================================================================================");

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
        CLOG.error("Invalid update type. Must be 'branch' or 'replace'.");
        sys.exit(1);
    # Check the update type

    if not os.path.exists(input_hal):
        CLOG.error(f"Input hal file {input_hal} does not exist. Exiting.");
        sys.exit(1);
    # Check the input hal file

    if not parent:
        CLOG.error("Parent/replacement genome not specified. Exiting.");
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
                CLOG.warning("Child genome specified for node update. This will be ignored.");
            # If a child genome is specified for a node update, ignore it
            command += ["--genome", parent];
        elif update_type == "branch":
            if not child:
                CLOG.error("Child genome not specified for branch update. Exiting.");
                sys.exit(1);
            # Check the child genome
            command += ["--parentGenome", parent, 
                        "--childGenome", child,
                        "--ancestorName", new_anc_name
                        ];

            if new_top_bl:
                command += ["--topBranchLength", str(new_top_bl)];
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

    CLOG.info(f"Command to run cactus-update-prepare: {' '.join(command)}");
    CLOG.debug("===================================================================================");
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
        CLOG.error(f"File not found: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        CLOG.error(f"Error running cactus-prepare: {e}");
        CLOG.debug(f"Command: {' '.join(command)}");
        CLOG.error(f"Check log file for more info: {logpath}");        
        sys.exit(1)
    # Run the command and check for errors

    CLOG.info(f"Successfully ran cactus-update-prepare.");# Parsing file names form {output_dir}/seq_file.out");

    # with open(os.path.join(output_dir, "seq_file.out")) as f:
    #     seq_files = [];
    #     next(f)  # Skip the first line
    #     for line in f:
    #         if not line.strip():
    #             continue;
    #         # Skip any blank lines
            
    #         line = line.strip().split("\t");
    #         if line[0] not in [parent, new_anc_name]:
    #             seq_files.append(line[1]);
    #             CLOG.debug(f"Adding seq file {line[1]} to list");
            # Add the seq files to the list if they are not the parent or new ancestor

    #return seq_files;
    # Return the preprocess file paths

#############################################################################