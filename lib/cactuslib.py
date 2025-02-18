#############################################################################
# Functions to help with the cactus gpu snakemake pipeline
#
# Gregg Thomas, April 2022
#############################################################################

import sys, os
import re
import requests
import subprocess
import logging
import lib.treelib as treelib

#############################################################################

cactuslib_logger = logging.getLogger('cactuslib')
# Create the logger

#############################################################################

def configureLogging(log_filename: str, log_level : str, log_verbosity: str) -> None:
# Set up logging for debugging the helper libraries and code not directly in the pipeline rules

    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S';
    # Format the log messages

    
    if not cactuslib_logger.hasHandlers():
    # Check if logger has handlers already (necessary to prevent duplicate handlers in some cases)        
        if log_verbosity in ["BOTH", "FILE"]:
            handler_file = logging.FileHandler(log_filename)
            handler_file.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
            cactuslib_logger.addHandler(handler_file)
        # Add file handler if specified

        if log_verbosity in ["BOTH", "SCREEN"]:
            handler_stderr = logging.StreamHandler()
            handler_stderr.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
            cactuslib_logger.addHandler(handler_stderr)
        # Add stream handler if specified

        if log_verbosity not in ["BOTH", "FILE", "SCREEN"]:
            raise ValueError("Invalid log verbosity: " + log_verbosity + ". Choose from BOTH, FILE, SCREEN.");
        # Set the logging level          

    
    log_level = log_level.upper()
    level_map = {
        'CRITICAL': logging.CRITICAL,
        'ERROR': logging.ERROR,
        'WARNING': logging.WARNING,
        'INFO': logging.INFO,
        'DEBUG': logging.DEBUG,
        'NOTSET': logging.NOTSET
    }
    # Map of string levels to logging module constants
    
    try:
        cactuslib_logger.setLevel(level_map[log_level])
        cactuslib_logger.debug(f"Logging level set to {log_level}")
    except KeyError:
        raise ValueError(f"Invalid logging level: {log_level}. Choose from {list(level_map.keys())}")
    # Set the logging level and handle invalid levels

#############################################################################

def turnOffLogger(log):
    for handler in log.handlers[:]:  # Handle a copy of handlers list
        log.removeHandler(handler)
        handler.close()

#############################################################################

def parseCactusVersion(tag):
    # Use regex to find all digit sequences in the tag name
    numbers = re.findall(r'\d+', tag)
    # Convert these sequences to integers for numeric comparison
    return tuple(map(int, numbers))

#############################################################################

def fetchLatestCactusTag(get_gpu: bool) -> str:
    url = 'https://quay.io/api/v1/repository/comparative-genomics-toolkit/cactus/tag/'

    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise SystemExit(e)

    tags_info = response.json().get('tags', [])

    # Extract tag names with a regex match for version-like strings
    pattern = re.compile(r'^v\d+\.\d+\.\d+(-gpu)?$')
    tags = [tag_info['name'] for tag_info in tags_info if pattern.match(tag_info['name'])]


    if get_gpu:
        # Filter GPU tags
        relevant_tags = [tag for tag in tags if '-gpu' in tag]
    else:
        # Filter non-GPU tags ignoring 'latest'
        relevant_tags = [tag for tag in tags if '-gpu' not in tag and tag != 'latest']

    try:
        # Find the latest version tag based on numeric comparison
        latest_version_tag = max(relevant_tags, key=parseCactusVersion)
    except ValueError:
        raise RuntimeError(f"No valid {'GPU' if use_gpu else 'non-GPU'} version tags found.")
    
    # Verify that the result is a valid string that fits the pattern
    if not isinstance(latest_version_tag, str) or not pattern.match(latest_version_tag):
        raise RuntimeError(f"Latest tag '{latest_version_tag}' does not match expected format.")

    cactuslib_logger.info(f"Latest {'GPU' if get_gpu else 'non-GPU'} version tag: {latest_version_tag}")
    return latest_version_tag

#############################################################################

def downloadCactusImage(use_gpu: bool) -> None:
    latest_tag = fetchLatestCactusTag(use_gpu)

    # Ensure there is a valid tag returned
    # if not latest_tag:
    #     print(f"No valid tag found for {'GPU' if use_gpu else 'non-GPU'} version.")
    #     return None

    image_uri = f"docker://quay.io/comparative-genomics-toolkit/cactus:{latest_tag}"

    # Define the image file name
    image_name = f"cactus_{latest_tag.replace('/', '_')}.sif"

    if os.path.exists(image_name):
        cactuslib_logger.warning(f"Image {image_name} already exists. This image will be used.")
        cactuslib_logger.debug("=" * 87);
        return os.path.abspath(image_name)

    else:
        # The singularity pull command with the output file name
        command = ['singularity', 'pull', '--disable-cache', image_name, image_uri]

        cactuslib_logger.info(f"Cactus image name to download: {image_name}")
        cactuslib_logger.info(f"Command to pull image: {' '.join(command)}")
        cactuslib_logger.debug("===================================================================================");

        try:
            subprocess.run(command, check=True)
            cactuslib_logger.info(f"Successfully pulled {image_uri} to {os.path.abspath(image_name)}")
            return os.path.abspath(image_name)
        except subprocess.CalledProcessError as e:
            cactuslib_logger.error(f"Failed to pull the image: {e}")
            sys.exit(1)


#############################################################################

def runCactusPrepare(input_file, cactus_path, output_dir, overwite_output_dir, output_hal, use_gpu):
# This function runs cactus-prepare on the input file and saves the output in the output directory

    if not os.path.exists(output_dir):
        cactuslib_logger.info(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir);
    elif os.path.exists(output_dir) and not overwite_output_dir:
        cactuslib_logger.error(f"Output directory already exists: {output_dir}. Set overwrite_output_dir to True in your config file to overwrite.")
        sys.exit(1);
    else:
        cactuslib_logger.info(f"Output directory {output_dir} already exists and overwrite_output_dir is True. Continuing.");
    # Make the output directory if it doesn't exist

    cactus_path_list = cactus_path.split(" ");

    command = cactus_path_list + ["cactus-prepare", input_file, "--outDir", output_dir, "--outHal", output_hal];
    if use_gpu:
        command.append("--gpu");
    # The command to run cactus-prepare

    cactuslib_logger.info(f"Command to run cactus-prepare: {' '.join(command)}");
    cactuslib_logger.debug("===================================================================================");
    # Debug output

    if use_gpu:
        logfile = "cactus-prepare-gpu.log";
    else:
        logfile = "cactus-prepare.log";
    logpath = os.path.join(output_dir, logfile);
    # The log file name

    try:
        with open(logpath, "w") as log_file:
            subprocess.run(command, check=True, stdout=log_file, stderr=subprocess.STDOUT)
    except FileNotFoundError as e:
        cactuslib_logger.error(f"File not found: {e}")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        cactuslib_logger.error(f"Error running cactus-prepare: {e}")
        sys.exit(1)
    # Run the command and check for errors


#############################################################################

def readTips(input_file):
# This function reads the cactus input file and initializes the tips dictionary
    
    tips = {};
    # The main dictionary for storing information and file paths for tips in the tree:
    # [output fasta file from mask step] : { 'input' : "original genome fasta file", 'name' : "genome name in tree", 'output' : "expected output from mask step (same as key)" }

    first = True;
    for line in open(input_file):
        if not line.strip():
            continue;
        # Skip any blank lines

        if first:
            cactuslib_logger.info(f"USER INPUT TREE: {line.strip()}");
            first = False;
            continue;
        # The first line contains the input tree... skip

        line = line.strip().split("\t");
        cur_base = os.path.basename(line[1]);
        tips[line[0]] = { 'input' : [line[1]], 'name' : line[0], 'output' : "NA" };
    ## Read the genome names and original genome fasta file paths from the same cactus input file used with cactus-prepare

    if cactuslib_logger.isEnabledFor(logging.DEBUG):
        cactuslib_logger.debug("TREE TIPS:");
        for g in tips:
            cactuslib_logger.debug(f"{g}: {tips[g]}")
        cactuslib_logger.debug("===================================================================================");
    ## Some output for debugging

    return tips;

#############################################################################

def initializeInternals(cactus_file, tips):
# This function reads the cactus file generated by cactus-prepare and initializes the internals dictionary

    internals = {};
    # The main dictionary for storing information and file paths for internal nodes in the tree:
    # [node name] : { 'name' : "node name in tree", 'blast-inputs' : [the expected inputs for the blast step], 'align-inputs' : [the expected inputs for the align step],
    #                   'hal-inputs' : [the expected inputs for the hal2fasta step], 'blast-output' : "the .cigar file output from the blast step",
    #                   'align-output' : "the .hal file output from the align step", 'hal-output' : "the fasta file output from the hal2fasta step" }

    first = True;
    for line in open(cactus_file):
        if not line.strip():
            continue;
        # Skip any blank lines

        if first:
            anc_tree = line.strip();
            first = False;
            continue;
        # The first line contains the tree with internal nodes labeled... save this for later

        line = line.strip().split("\t");
        name = line[0];
        cur_base = os.path.basename(line[1]);

        if name in tips:
            tips[name]['output'] = cur_base;
        else:
            internals[name] = {  'name' : name, 
                                    'input-seqs' : "NA", 
                                    'hal-file' : cur_base.replace(".fa", ".hal"), 
                                    'cigar-file' : cur_base.replace(".fa", ".cigar"), 
                                    'seq-file' : cur_base };
    ## Read the internal node labels and output file paths from the file generated by cactus-prepare

    cactuslib_logger.info(f"CACTUS LABELED TREE: {anc_tree}");

    return internals, anc_tree;

#############################################################################

def parseInternals(internals, tips, tinfo, anc_tree):
# This function parses the cactus tree with internal node labels and updates the internals dictionary 
# with the round and input sequences for each internal node

    internal_nodes = [ n for n in tinfo if tinfo[n][2] != 'tip' ];
    # Parse the tree with the internal node labels

    tip_list = list(tips.keys());

    ####################

    for node in internal_nodes:
        name = tinfo[node][3];
        # The cactus node label

        internals[name]['round'] = treelib.maxDistToTip(node, tinfo);
    ## One loop through the tree to get the round each node is in based on its maximum
    ## distance to a tip

    ####################

    for node in internal_nodes:
        name = tinfo[node][3];
        # Get the name of the current node

        expected_seq_inputs = [];
        # We will construct a list of all sequences required as input for this node -- all those
        # from nodes in the previous round

        cur_desc = treelib.getDesc(node, tinfo);
        # Get descendant nodes for the current node

        for tip in tips:
            expected_seq_inputs.append(tips[tip]['output']);

        if not all(tinfo[desc][2] == "tip" for desc in cur_desc):
            for node_check in internal_nodes:
                name_check = tinfo[node_check][3];
                #print(node, name, node_check, name_check)
                if internals[name]['round']-1 != internals[name_check]['round']:
                    continue;
                expected_seq_inputs.append(internals[name_check]['seq-file']);
                # Go through the internal nodes again and skip any that aren't in the previous round  

        internals[name]['input-seqs'] = expected_seq_inputs;
        # Add the expected input seqs to the main internals dict for this node       
    ## Another loop through the tree to get the input sequences for each node

    if cactuslib_logger.isEnabledFor(logging.DEBUG):
        cactuslib_logger.debug("TREE INTERNAL NODES:");
        for g in internals:
            cactuslib_logger.debug(f"{g}: {internals[g]}");
        cactuslib_logger.debug("===================================================================================");
    ## Some output for debugging

    return internals;

#############################################################################    