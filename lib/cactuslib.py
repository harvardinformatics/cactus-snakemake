#############################################################################
# Functions to help with the cactus gpu snakemake pipeline
#
# Gregg Thomas, April 2022
#############################################################################

import sys
import os
import shutil
import re
import requests
import subprocess
import logging
from datetime import datetime
import yaml
import traceback

#############################################################################

cactuslib_logger = logging.getLogger('cactuslib')
# Get the logger for the cactuslib module

#############################################################################

# Example of your ColoredFormatter
class ColoredFormatter(logging.Formatter):
    RESET = "\033[0m"
    COLOR_MAP = {
        logging.DEBUG: "\033[35m",      # Purple (Magenta) for DEBUG
        logging.INFO: "\033[36m",       # Cyan for INFO
        logging.WARNING: "\033[33m",    # Yellow for WARNING
        logging.ERROR: "\033[31m",      # Red for ERROR
        logging.CRITICAL: "\033[1;31m"    # Bold red for CRITICAL
    }

    def format(self, record):
        color = self.COLOR_MAP.get(record.levelno, self.RESET)
        message = super().format(record)
        return f"{color}{message}{self.RESET}"

# Define the filter that will block records flagged as file_only.
def no_file_only(record):
    return not getattr(record, 'file_only', False)

# Assume cactuslib_logger is created earlier:
cactuslib_logger = logging.getLogger('cactuslib')

def configureLogging(log_filename: str, log_level: str, log_verbosity: str) -> None:
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Check if logger has handlers already to avoid duplicate handlers
    if not cactuslib_logger.hasHandlers():
        if log_verbosity in ["BOTH", "FILE"]:
            handler_file = logging.FileHandler(log_filename)
            handler_file.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
            cactuslib_logger.addHandler(handler_file)
        # Add file handler if specified

        if log_verbosity in ["BOTH", "SCREEN"]:
            # Create a handler for DEBUG and INFO messages that prints to stdout
            handler_stdout = logging.StreamHandler(sys.stdout)
            handler_stdout.setFormatter(ColoredFormatter(fmt=log_format, datefmt=date_format))
            # Only allow messages with level less than WARNING (DEBUG, INFO)
            handler_stdout.addFilter(lambda record: record.levelno < logging.WARNING)
            # And add our extra filter to skip file-only records
            handler_stdout.addFilter(no_file_only)
            cactuslib_logger.addHandler(handler_stdout)

            # Create a separate handler for WARNING and above that prints to stderr
            handler_stderr = logging.StreamHandler(sys.stderr)
            handler_stderr.setFormatter(ColoredFormatter(fmt=log_format, datefmt=date_format))
            # Only allow messages with level WARNING or higher
            handler_stderr.addFilter(lambda record: record.levelno >= logging.WARNING)
            # Also add our filter here to skip file-only records
            handler_stderr.addFilter(no_file_only)
            cactuslib_logger.addHandler(handler_stderr)

        if log_verbosity not in ["BOTH", "FILE", "SCREEN"]:
            raise ValueError("Invalid log verbosity: " + log_verbosity + ". Choose from BOTH, FILE, SCREEN.")
    
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
    try:
        cactuslib_logger.setLevel(level_map[log_level])
        cactuslib_logger.debug(f"Logging level set to {log_level}")
    except KeyError:
        raise ValueError(f"Invalid logging level: {log_level}. Choose from {list(level_map.keys())}")


#############################################################################

def getInfo(version_flag, info_flag, args):
    color = "\033[36m"; # cyan
    reset_color = "\033[0m";
    # Some color codes for printing

    info_path = os.path.join(os.path.dirname(__file__), "info.yaml")
    with open(info_path, "r") as file:
        info = yaml.safe_load(file);
    # Read the meta info from the info.yaml file

    if version_flag:
        print(f"\n{color}Snakemake cactus pipeline version {info['version']} released on {info['releasedate-patch']}{reset_color}");
        sys.exit();
    # If the version flag is set, print the version and exit

    if info_flag:
        snakefile = "";
        if '-s' in args:
            idx = args.index('-s');
            if idx + 1 < len(args):
                snakefile = args[idx + 1];
        elif '--snakefile' in args:
            idx = args.index('--snakefile');
            if idx + 1 < len(args):
                snakefile = args[idx + 1];
        # Try to get the path to the snakefile

        snakefile_path = os.path.abspath(snakefile);
        mod_timestamp = os.path.getmtime(snakefile_path);
        mod_datetime = datetime.fromtimestamp(mod_timestamp);
        # Get the last modified date of the snakefile

        print(f"\n{color}---Snakemake cactus pipeline---{reset_color}")
        for key, value in info.items():
            if key == "latest-commit-msg":
                continue;
            if value:
                print(f"{color}{key}: {value}{reset_color}");

                if key == "latest-commit-date" and snakefile:
                    print(f"{color}{os.path.basename(snakefile)} last modified: {mod_datetime.date()}{reset_color}");
                # Print the last modified date of the snakefile if it exists
        sys.exit();
    # If the info flag is set, print the meta info and exit

#############################################################################

def pipelineSetup(config, args, version_flag, info_flag, config_flag, debug, workflow, pad=50):
    main_flag = True;
    if "__main__.py" in args[0]:
        main_flag = False;
    # Whether the pipeline is being run as a main script or not 

    if main_flag and version_flag or info_flag:
        info = getInfo(version_flag, info_flag, args);
    # Print version or info if specified, which will terminate the program early

    dry_run_flag = False;
    if any([arg in args for arg in ["--dry-run", "--dryrun", "-n"]]):
        dry_run_flag = True;
    # Whether the pipeline is running in dry-run mode

    log_level = "info";
    if any([arg in args for arg in ["--rulegraph", "--dag"]]):
        log_level = "notset";
    if debug or config_flag:
        log_level = "debug";
    # Set the log level based on the arguments

    #output_dir_cfg = os.path.abspath(config["output_dir"]);
    output_dir = os.path.abspath(config["output_dir"]);
    # if dry_run_flag:
    #     import atexit, shutil
    #     output_dir = os.path.join("/tmp/", "cactus-smk-dryrun");
    #     atexit.register(lambda: shutil.rmtree(output_dir, ignore_errors=True));
    log_dir = os.path.join(output_dir, "logs");
    # The output directory where all the files and logs are stored

    if main_flag and not version_flag or not info_flag:
        outdir_log_msg, outdir_err_flag = createOutputDirs(output_dir, log_dir, dry_run_flag);
    # Create the output directories if they don't exist

    log_verbosity = "both"; # "screen", "file", "both"
    if dry_run_flag:
        log_verbosity = "screen";
    # Set the log verbosity based on the arguments

    log_filename = os.path.join(log_dir, f"cactus-snakemake.{log_level}.log"); # Log file name if log_verbosity is "file" or "both"
    configureLogging(log_filename, log_level.upper(), log_verbosity.upper());
    cactuslib_logger = logging.getLogger('cactuslib')
    # Set up the logger

    if config_flag or debug:
        debug_pad = pad - 1;
        cactuslib_logger.debug(spacedOut("Config file", debug_pad) + os.path.abspath(workflow.configfiles[0])); 
        cactuslib_logger.debug("---");   
        for key, value in config.items():
            cactuslib_logger.debug(spacedOut(key, debug_pad) + str(value));
        cactuslib_logger.debug("=" * 80);
        if config_flag:
            sys.exit();

    if main_flag:
        cactuslib_logger.info(f"MAIN call: {' '.join(args)}");
        # Log the command that was run to start the pipeline

        if outdir_err_flag:
            cactuslib_logger.error(outdir_log_msg);
            sys.exit(1);
        else:
            cactuslib_logger.info(outdir_log_msg);
        # Log the command that was run to create the output directory
        target_jobs = None;
    else:
        target_jobs = None
        if "--target-jobs" in args:
            target_jobs_index = args.index("--target-jobs")
            if target_jobs_index + 1 < len(args):
                target_jobs = args[target_jobs_index + 1];
                if target_jobs[-1] == ":":
                    target_jobs = target_jobs[:-1];
        cactuslib_logger.info(f"RULE {target_jobs} call: {' '.join(args)}", extra={'file_only': True});
        # Log the command that was run for a rule

    tmp_dir = config["tmp_dir"];
    if not os.path.exists(tmp_dir):
        if main_flag:
            cactuslib_logger.info(f"Creating temporary directory at {tmp_dir}");
        os.makedirs(tmp_dir);
    # A directory with lots of space to use for temporary files generated by the cactus-align command

    return main_flag, dry_run_flag, output_dir, log_dir, tmp_dir, log_level, log_verbosity

#############################################################################

def fmtDT():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def fmtDTLog():
    return datetime.now().strftime('%Y%m%d%H%M%S')

#############################################################################

def turnOffLogger(log):
    for handler in log.handlers[:]:  # Handle a copy of handlers list
        log.removeHandler(handler)
        handler.close()

#############################################################################

def createOutputDirs(outdir, logdir, dry_run, outdir_cfg=""):
    err_flag = False;

    outdir_exists = os.path.exists(outdir);

    # if dry_run:
    #     msg = f"Output directory {outdir_cfg} will be created.";
    # else:
    if not outdir_exists:
        os.makedirs(outdir);
        msg = f"Created output directory: {outdir}";
    # elif outdir_exists and not overwite_output_dir:
    #     msg = f"Output directory already exists: {outdir}. Remove the directory or set overwrite_output_dir to True in your config file to use it anyway and potentially overwrite files from previous runs.";
    #     err_flag = True;
    else:
        msg = f"Output directory {outdir} already exists. Continuing.";
    # Logging for the output directory        
    # Make the output directory if it doesn't exist

    if not os.path.exists(logdir):
        os.makedirs(logdir);
    # Make the log directory if it doesn't exist. This has to be done before the rest
    # so the logging works

    return msg, err_flag;

#############################################################################

def parseCactusVersion(tag):
    # Use regex to find all digit sequences in the tag name
    numbers = re.findall(r'\d+', tag)
    # Convert these sequences to integers for numeric comparison
    return tuple(map(int, numbers))

#############################################################################

def fetchLatestCactusTag(get_gpu: bool, main: bool, pad: int) -> str:
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

    if main:
        cactuslib_logger.info(spacedOut(f"Latest {'GPU' if get_gpu else 'non-GPU'} version tag", pad) + f"{latest_version_tag}")
    return latest_version_tag

#############################################################################

def downloadCactusImage(use_gpu: bool, main: bool, pad: int, tag: str="") -> None:
    if not tag:
        tag = fetchLatestCactusTag(use_gpu, main, pad);
    else:
        if tag[0] != "v":
            tag = "v" + tag;
        if use_gpu:
            tag = tag + "-gpu";
    #latest_tag = fetchLatestCactusTag(use_gpu, main)

    # Ensure there is a valid tag returned
    # if not latest_tag:
    #     print(f"No valid tag found for {'GPU' if use_gpu else 'non-GPU'} version.")
    #     return None

    image_uri = f"docker://quay.io/comparative-genomics-toolkit/cactus:{tag}"

    # Define the image file name
    image_name = f"cactus_{tag.replace('/', '_')}.sif"

    if os.path.exists(image_name):
        if main:
            cactuslib_logger.info(f"Image {image_name} already exists. This image will be used.")
            cactuslib_logger.debug("=" * 83);
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

def parseCactusPath(cactus_cfg: str, use_gpu: bool, main: bool, pad: int) -> None:
    version_tag_pattern = r"^v?\d+(\.\d+)+$";

    if cactus_cfg == None or cactus_cfg.lower() in ["download", ""]:
        cactus_image_path = downloadCactusImage(False, main, pad);
        # Download the latest cactus image if it is not specified in the config file
    elif re.match(version_tag_pattern, cactus_cfg) is not None:
        cactus_image_path = downloadCactusImage(False, main, pad, cactus_cfg);
        # Pass a specific version tag to download
    else:
        cactus_image_path = cactus_cfg;
        # The local path to the cactus image

        if not os.path.exists(cactus_image_path):
            cactuslib_logger.error(f"Could not find cactus image at {cactus_image_path}");
            sys.exit(1);
        # Check if the cactus image exists
    ## Non-GPU image

    if use_gpu:
        if cactus_cfg == None or cactus_cfg.lower() in ["download", ""]:
            cactus_gpu_image_path = downloadCactusImage(True, main, pad);
            # Download the latest cactus image if it is not specified in the config file
        elif re.match(version_tag_pattern, cactus_cfg) is not None:
            cactus_gpu_image_path = downloadCactusImage(True, main, pad, cactus_cfg);
            # Pass a specific version tag to download
        else:
            cactus_gpu_image_path = cactus_cfg;
            # The local path to the cactus image

            if not os.path.exists(cactus_gpu_image_path):
                cactuslib_logger.error(f"Could not find cactus image at {cactus_gpu_image_path}");
                sys.exit(1);
            # Check if the cactus image exists
    ## GPU image
    else:
        cactus_gpu_image_path = cactus_image_path;
    # If not using GPU, set the cactus GPU image path to the cactus image path


    return cactus_image_path, cactus_gpu_image_path;

#############################################################################

def runCactusPrepare(input_file, cactus_path, output_dir, output_hal, use_gpu, log_dir, dry_run):
# This function runs cactus-prepare on the input file and saves the output in the output directory

    log_prefix = "cactus-prepare";
    # if dry_run:
        # output_dir = "/tmp/cactus-smk-dryrun/";
        # os.makedirs(output_dir, exist_ok=True);
        # log_prefix = os.path.join(output_dir, "cactus-prepare");
    # If this is a dry run, create a temporary output directory and log file

    command = cactus_path + ["cactus-prepare", input_file, "--outDir", output_dir, "--outHal", output_hal];
    if use_gpu:
        command.append("--gpu");
    # The command to run cactus-prepare

    cactuslib_logger.info(f"Command to run cactus-prepare: {' '.join(command)}");
    cactuslib_logger.debug("===================================================================================");
    # Debug output

    if use_gpu:
        logfile = log_prefix + "-gpu.log";
    else:
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
        cactuslib_logger.error(f"Error running cactus-prepare: {e}")
        sys.exit(1)
    # Run the command and check for errors

    return os.path.join(output_dir, os.path.basename(input_file));
    # Return the output file path

#############################################################################

def spacedOut(string, totlen, sep="."):
# Properly adds spaces to the end of a message to make it a given length
    spaces = sep * (totlen - len(string));
    if len(string) > totlen:
        spaces += sep * 4;
    return string + spaces + " ";

def printWrite(string, stream):
    if "- INFO -" in string:
        color = "\033[36m"; # cyan
    elif "- ERROR -" in string:
        color = "\033[31m"; # red
    reset_color = "\033[0m";
    color_string = color + string + reset_color;
    # Format the string with color codes

    print(color_string, flush=True);
    stream.write(string + "\n");
    stream.flush();
# For logging in runCommand(), print the string and write it to the file stream

def writeFlush(string, stream):
    stream.write(string + "\n");
    stream.flush();
# For logging in runCommand(), write the string to the file stream

#############################################################################

def getResources(config, rule_name, keys=("partition", "mem_mb", "cpus", "time")):
# Return dict of all requested resource keys for a rule (with fallback to defaults).
    
    slurm_resource_map = { "partition" : "slurm_partition", "mem_mb" : "mem_mb", 
                            "cpus" : "cpus_per_task", "time" : "runtime" };
    # Because I use slightly different resource names from what snakemake does for slurm

    rule_resources = {
        slurm_resource_map[resource] : getResource(config, rule_name, resource)
        for resource in keys
    }

    # for key, value in rule_resources.items():
    #     meta_logger.info(f"Rule {rule_name} resource '{key}' set to {value}");

    return rule_resources

def getResource(config, rule_name, resource):
    # Get a specific resource value from the Snakemake config.yaml.
    rule_val = config.get("rule_resources", {}).get(rule_name, {}).get(resource)
    default_val = config.get("rule_resources", {}).get("default", {}).get(resource)

    if rule_val is not None:
        return rule_val
    elif default_val is not None:
        return default_val
    else:
        meta_logger.error(f"Missing resource '{resource}' for rule '{rule_name}' and no default set.");
        raise ValueError();


#############################################################################    

def runCommand(cmd, tmpdir, logfile, rule, wc="", fmode="w+"):

    if wc:
        wc = "-" + wc;
    # If a wild card is specified, add a hyphen so it is formatted
    # nicer in the print statements

    restart = False;

    with open(logfile, fmode) as logfile_stream:
        if tmpdir:
            printWrite(f"{fmtDT()} - RULE {rule}{wc} - INFO - runCommand0 - Checking for tmp dir: {tmpdir} - {os.path.isdir(tmpdir)}", logfile_stream);
            if os.path.isdir(tmpdir):
                cmd = cmd + ["--restart"];
                restart = True;
        # If the tmp dir exists, add the --restart flag to the command

        printWrite(f"{fmtDT()} - RULE {rule}{wc} - INFO - runCommand1 - Running command: {' '.join(cmd)}", logfile_stream);
        writeFlush("-" * 20 + " COMMAND LOG BEGIN " + "-" * 20 + "\n", logfile_stream);
        proc = subprocess.run(cmd, stdout=logfile_stream, stderr=logfile_stream);
        writeFlush("-" * 20 + "  COMMAND LOG END  " + "-" * 20 + "\n", logfile_stream);
            
    # Run the command and write the output to the log file
    
        rcode = proc.returncode;
        # Get the return code

        if not restart and rcode != 0:
            tb = traceback.format_exc()
            printWrite(f"{fmtDT()} - RULE {rule}{wc} - ERROR - runCommand2 - Command failed: {' '.join(cmd)}", logfile_stream);
            printWrite(f"{fmtDT()} - RULE {rule}{wc} - ERROR - Traceback:\n{tb}", logfile_stream);
            raise;            
        # If the command failed without a restart, raise an exception

        elif restart and rcode != 0:
        # If the command failed with a restart, check the log file to see if the error was a FileNotFoundError

            logfile_stream.seek(0)
            log_data = logfile_stream.read();
            # Reset the file pointer to the beginning of the log file and read what has been written so 
            # we can see if a certain error has ocurred.

            if "FileNotFoundError: [Errno 2] No such file or directory:" in log_data:       
                printWrite(f"{fmtDT()} - RULE {rule}{wc} - INFO - runCommand3 - --restart failed with FileNotFoundError. Removing job tmp dir and trying again without --restart.", logfile_stream);
                shutil.rmtree(tmpdir, ignore_errors=True);

                cmd = cmd[:-1] if cmd[-1] == "--restart" else cmd;
                # Remove the --restart flag from the command if present (it should be at this point)

                printWrite(f"{fmtDT()} - RULE {rule}{wc} - INFO - runCommand4 - Running command: {' '.join(cmd)}", logfile_stream);
                writeFlush("-" * 20 + " COMMAND LOG BEGIN " + "-" * 20 + "\n", logfile_stream);
                proc = subprocess.run(cmd, stdout=logfile_stream, stderr=logfile_stream);
                writeFlush("-" * 20 + "  COMMAND LOG END  " + "-" * 20 + "\n", logfile_stream);
            # If the error was a FileNotFoundError, remove the tmp dir and try the command again, without the --restart flag

                if proc.returncode != 0:
                    tb = traceback.format_exc()
                    printWrite(f"{fmtDT()} - RULE {rule}{wc} - ERROR - runCommand5 - Command failed even without --restart: {' '.join(cmd)}. Removing job tmp dir and exiting.", logfile_stream);
                    printWrite(f"{fmtDT()} - RULE {rule}{wc} - ERROR - Traceback:\n{tb}", logfile_stream);
                    shutil.rmtree(tmpdir, ignore_errors=True);
                    raise;
                # If the command failed again, raise an exception

            else:
                tb = traceback.format_exc()
                printWrite(f"{fmtDT()} - RULE {rule}{wc} - ERROR - runCommand6 - --restart failed with an error other than FileNotFoundError. Exiting.", logfile_stream);
                printWrite(f"{fmtDT()} - RULE {rule}{wc} - ERROR - Traceback:\n{tb}", logfile_stream);
                raise;
            # If the error with a --restart, but not a FileNotFoundError, raise an exception

#############################################################################