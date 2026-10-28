#############################################################################
# Functions for the prep step of the cactus snakemake pipelines.
#
# Prep runs once, only when asked for (--config prep=T): it resolves the cactus
# image, runs cactus-prepare (or the pipeline's equivalent), and records what it
# did in a manifest in the output directory. Every other run of the pipeline,
# including each cluster job, only reads that manifest and stops if it is
# missing or no longer matches the config and input files.
#
# Gregg Thomas, October 2026
#############################################################################

import sys
import os
import hashlib
import logging
import yaml

import lib.cactuslib as CACTUSLIB
import lib.treelib as TREELIB
from lib.cactuslib import spacedOut as SO

#############################################################################

CLOG = logging.getLogger('cactuslib')
# Get the logger for the cactuslib module

MANIFEST_NAME = "prep-manifest.yaml";
# The manifest prep writes to the output directory

#############################################################################

def manifestPath(output_dir):
    return os.path.join(output_dir, MANIFEST_NAME);

#############################################################################

def hashFile(path):
# Returns the sha256 of a file. Only used on small files (input files and seqfiles),
# never on genomes or HALs, since it runs every time a Snakefile is parsed.

    sha256 = hashlib.sha256();
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha256.update(chunk);
    return sha256.hexdigest();

#############################################################################

def getVersion():
# Reads the cactus-snakemake version from lib/info.yaml, to record in the manifest

    info_path = os.path.join(os.path.dirname(__file__), "info.yaml");
    with open(info_path, "r") as f:
        info = yaml.safe_load(f);
    return str(info['version']);

#############################################################################

def fingerprint(pipeline, config):
# The config values and input file contents a pipeline's prep step depends on. If any of these
# change after prep, the prep outputs (and anything built from them) may no longer match.

    fp = { "cactus_path" : str(config.get("cactus_path")),
            "use_gpu" : bool(config.get("use_gpu", False)) };
    # Every pipeline's prep resolves the cactus image

    if pipeline == "align":
        fp["input_file_sha256"] = hashFile(os.path.abspath(config["input_file"]));
    # cactus-prepare's output depends on the whole input file: the tree and the genome paths

    return fp;

#############################################################################

def compareFingerprint(prepped_fp, current_fp):
# Lists every fingerprint value that differs between prep time and now

    mismatches = [];
    for key in sorted(set(prepped_fp) | set(current_fp)):
        prepped_val = prepped_fp.get(key);
        current_val = current_fp.get(key);
        if prepped_val == current_val:
            continue;

        if key.endswith("_sha256"):
            mismatches.append(f"{key[:-len('_sha256')]}: contents have changed since prep");
        else:
            mismatches.append(f"{key}: was {prepped_val!r} at prep, config now has {current_val!r}");

    return mismatches;

#############################################################################

def checkGeneratedFiles(generated_files, output_dir):
# Lists every file prep wrote that is now missing or has changed since prep

    mismatches = [];
    for rel_path, prepped_hash in generated_files.items():
        path = os.path.join(output_dir, rel_path);
        if not os.path.isfile(path):
            mismatches.append(f"{rel_path}: written by prep, but no longer exists");
        elif hashFile(path) != prepped_hash:
            mismatches.append(f"{rel_path}: has been modified since prep");

    return mismatches;

#############################################################################

def checkManifest(manifest, pipeline, config, output_dir):
# All the reasons an existing manifest can't be used for this run. An empty list means it can.

    if manifest.get("pipeline") != pipeline:
        return [f"pipeline: this output directory was prepped for '{manifest.get('pipeline')}', not '{pipeline}'"];
    # Nothing else is comparable if the manifest is for a different pipeline

    mismatches = compareFingerprint(manifest["fingerprint"], fingerprint(pipeline, config));
    mismatches += checkGeneratedFiles(manifest["generated_files"], output_dir);

    if not os.path.isfile(manifest["cactus_image"]):
        mismatches.append(f"cactus_image: {manifest['cactus_image']} no longer exists");
    # Jobs run this exact image, so it has to still be there

    return mismatches;

#############################################################################

def buildManifest(pipeline, config, cactus_image, version_tag, command, generated_files, output_dir):
# The record of one prep run. Generated files are stored relative to the output directory,
# with their sha256, so later runs can tell if they were changed or regenerated.

    return { "pipeline" : pipeline,
                "cactus_snakemake_version" : getVersion(),
                "created" : CACTUSLIB.fmtDT(),
                "cactus_image" : cactus_image,
                "cactus_version_tag" : version_tag,
                "fingerprint" : fingerprint(pipeline, config),
                "prepare_command" : " ".join(command) if command else None,
                "generated_files" : { os.path.relpath(f, output_dir) : hashFile(f) for f in generated_files } };

#############################################################################

def readManifest(manifest_file):
    with open(manifest_file, "r") as f:
        return yaml.safe_load(f);

def writeManifest(manifest, manifest_file):
    with open(manifest_file, "w") as f:
        f.write("# Written by the cactus-snakemake prep step. Do not edit: every run checks it against the config and input files.\n");
        yaml.safe_dump(manifest, f, sort_keys=False);

#############################################################################

def prepAlign(config, cactus_path, use_gpu, output_dir, log_dir, pad):
# Prep for cactus.smk: runs cactus-prepare to label the tree's internal nodes and write the
# seqfile the rest of the pipeline reads, then checks the result

    input_file = os.path.abspath(config["input_file"]);

    cactus_file, command = CACTUSLIB.runCactusPrepare(input_file, cactus_path, output_dir, None, use_gpu, log_dir, False);
    # output_hal and dry_run are not used by runCactusPrepare

    tips = TREELIB.readTips(input_file, False, pad);
    internals, anc_tree = TREELIB.initializeInternals(cactus_file, tips, False, pad);
    # Parse the result the same way the Snakefile will

    missing_tips = [ name for name in tips if tips[name]['output'] == "NA" ];
    if missing_tips:
        CLOG.error(f"cactus-prepare output {cactus_file} has no sequence file for: {', '.join(missing_tips)}");
        sys.exit(1);
    # Every genome in the input file must appear in cactus-prepare's output

    if config["maf_reference"] not in tips:
        CLOG.error(f"maf_reference '{config['maf_reference']}' is not one of the genomes in {input_file}: {', '.join(tips)}");
        sys.exit(1);
    # Catch a bad MAF reference now, rather than after the whole alignment has run

    return [cactus_file], command;

#############################################################################

def runPrep(pipeline, config, output_dir, log_dir, tmp_dir, main, pad, force=False):
# Runs the prep step for a pipeline and writes its manifest, unless a matching manifest already exists

    manifest_file = manifestPath(output_dir);

    if os.path.isfile(manifest_file):
        mismatches = checkManifest(readManifest(manifest_file), pipeline, config, output_dir);

        if not mismatches:
            CLOG.info(SO("Prep is already up to date", pad) + manifest_file);
            return;
        # Nothing to do if the manifest still matches

        if not force:
            CLOG.error(f"Prep has already been run for {output_dir}, but these no longer match:");
            for mismatch in mismatches:
                CLOG.error(f"    {mismatch}");
            CLOG.error("Files in the output directory were made from the earlier prep. To prep again anyway, add prep_force=T to --config.");
            sys.exit(1);
        # A stale manifest is an error unless re-prepping was explicitly asked for

        CLOG.warning(f"prep_force is set: running prep again for {output_dir}. These had changed:");
        for mismatch in mismatches:
            CLOG.warning(f"    {mismatch}");
        CLOG.warning("Intermediate files already in the output directory were made from the earlier prep and may not match the new one. Nothing is deleted.");
    ## Check any existing manifest first

    use_gpu = bool(config.get("use_gpu", False));

    cactus_image, version_tag = CACTUSLIB.resolveCactusImage(config["cactus_path"], use_gpu, main, pad);
    cactus_path, cactus_path_tmp = CACTUSLIB.buildCactusCommands(cactus_image, use_gpu, tmp_dir, config.get("singularity_bind_paths", []));
    # Resolve the cactus image once; every later run reads its path from the manifest

    if pipeline == "align":
        generated_files, command = prepAlign(config, cactus_path, use_gpu, output_dir, log_dir, pad);
    else:
        CLOG.error(f"No prep step is defined for pipeline '{pipeline}'.");
        sys.exit(1);
    # Run the pipeline-specific prep

    manifest = buildManifest(pipeline, config, cactus_image, version_tag, command, generated_files, output_dir);
    writeManifest(manifest, manifest_file);
    CLOG.info(SO("Wrote prep manifest", pad) + manifest_file);

#############################################################################

def requirePrep(pipeline, config, output_dir, main, pad, snakefile, configfiles):
# Loads the prep manifest for this output directory, or stops if prep hasn't been run or no
# longer matches. Runs on every parse of the Snakefile, so it only reads small files.

    manifest_file = manifestPath(output_dir);
    prep_cmd = f"snakemake -s {snakefile} --configfile {' '.join(configfiles)} --config prep=T";
    # The command to run prep, for the error messages

    if not os.path.isfile(manifest_file):
        CLOG.error(f"No prep manifest found at {manifest_file}.");
        CLOG.error("Prep must be run once for this output directory before the pipeline can run:");
        CLOG.error(f"    {prep_cmd}");
        sys.exit(1);

    manifest = readManifest(manifest_file);
    mismatches = checkManifest(manifest, pipeline, config, output_dir);
    if mismatches:
        CLOG.error(f"The prep manifest at {manifest_file} no longer matches this run:");
        for mismatch in mismatches:
            CLOG.error(f"    {mismatch}");
        CLOG.error("Files in the output directory were made from that prep. If the change is intended, prep again with:");
        CLOG.error(f"    {prep_cmd} prep_force=T");
        sys.exit(1);

    if main:
        CLOG.info(SO("Using prep manifest", pad) + manifest_file);
        CLOG.info(SO("Cactus image", pad) + f"{manifest['cactus_image']} ({manifest['cactus_version_tag']})");

    return manifest;

#############################################################################
