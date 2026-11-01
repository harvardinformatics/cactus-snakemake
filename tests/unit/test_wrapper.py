#############################################################################
# Tier-1 tests for the cactus_snakemake wrapper's argument handling and its
# conda-free commands (help, init, version). Each test runs the real script with
# bash in a subprocess.
#
# Nothing here creates, updates or activates a conda environment: prep and run are
# only tested for argument errors, which the wrapper reports before touching conda,
# and check only against an environment name that doesn't exist. setup, update and
# successful prep/run are checked by hand (see the plan's Phase 3 manual check).
#############################################################################

import os
import shutil
import subprocess

import pytest
import yaml

from tests.helpers import REPO_ROOT

WRAPPER = os.path.join(REPO_ROOT, "cactus_snakemake")

# An environment name that won't exist, so nothing can accidentally run against a real one
NO_ENV = "cactus-snakemake-no-such-env-for-tests"

TEMPLATES = {
    "align": "config-template.yaml",
    "add-genome": "add-genome-config-template.yaml",
    "replace-genome": "replace-genome-config-template.yaml",
    "add-outgroup": "add-outgroup-config-template.yaml",
    "minigraph": "minigraph-config-template.yaml",
}


def wrapper(*args, cwd=None):
    result = subprocess.run(["bash", WRAPPER, "--env-name", NO_ENV, *args], capture_output=True, text=True, cwd=cwd)
    return result.returncode, result.stdout, result.stderr

#############################################################################
# Help and dispatch

def test_help():
    rc, stdout, _ = wrapper("help")
    assert rc == 0
    assert "Usage:" in stdout
    for pipeline in TEMPLATES:
        assert pipeline in stdout


def test_no_command_shows_usage_and_fails():
    rc, _, stderr = wrapper()
    assert rc == 1
    assert "Usage:" in stderr


def test_unknown_command():
    rc, _, stderr = wrapper("align")
    assert rc == 1
    assert "Unknown command: 'align'" in stderr


@pytest.mark.parametrize("command", ["init", "prep", "run"])
def test_missing_pipeline(command):
    rc, _, stderr = wrapper(command)
    assert rc == 1
    assert "a pipeline name is required" in stderr


@pytest.mark.parametrize("command", ["init", "prep", "run"])
def test_unknown_pipeline(command):
    rc, _, stderr = wrapper(command, "update")
    assert rc == 1
    assert "unknown pipeline 'update'" in stderr


def test_global_option_after_command_is_rejected():
    # --env-name must come before the command, so it can never be mistaken for a run argument
    rc, _, stderr = wrapper("check", "--env-name", "other")
    assert rc == 1
    assert "unknown argument '--env-name'" in stderr

#############################################################################
# run and prep argument errors (reported before the conda environment is touched)

@pytest.mark.parametrize("snakefile_arg", [["-s", "cactus.smk"], ["--snakefile", "cactus.smk"], ["--snakefile=cactus.smk"]])
def test_run_rejects_snakefile(snakefile_arg):
    rc, _, stderr = wrapper("run", "align", "--configfile", "x.yaml", *snakefile_arg)
    assert rc == 1
    assert "don't pass -s/--snakefile" in stderr


def test_prep_requires_configfile():
    rc, _, stderr = wrapper("prep", "align")
    assert rc == 1
    assert "--configfile is required" in stderr


def test_prep_rejects_other_arguments(tmp_path):
    rc, _, stderr = wrapper("prep", "align", "--configfile", str(tmp_path / "x.yaml"), "--config", "debug=T")
    assert rc == 1
    assert "unknown argument '--config'" in stderr


def test_prep_missing_configfile(tmp_path):
    missing = str(tmp_path / "not-written.yaml")
    rc, _, stderr = wrapper("prep", "align", "--configfile", missing)
    assert rc == 1
    assert f"config file '{missing}' not found" in stderr

#############################################################################
# init

@pytest.mark.parametrize("pipeline", list(TEMPLATES))
def test_init_copies_template(tmp_path, pipeline):
    out = tmp_path / "my-config.yaml"
    rc, stdout, stderr = wrapper("init", pipeline, "-o", str(out))
    assert rc == 0, stderr
    assert f"prep {pipeline} --configfile" in stdout

    # A short header, then the template exactly
    with open(os.path.join(REPO_ROOT, "config-templates", TEMPLATES[pipeline])) as f:
        template = f.read()
    written = out.read_text()
    assert written.startswith(f"# Starter config for the cactus-snakemake {pipeline} pipeline")
    assert written.endswith(template)


def test_init_default_output(tmp_path):
    rc, _, stderr = wrapper("init", "minigraph", cwd=tmp_path)
    assert rc == 0, stderr
    assert (tmp_path / "minigraph-config.yaml").is_file()


def test_init_does_not_overwrite_without_force(tmp_path):
    out = tmp_path / "my-config.yaml"
    out.write_text("cactus_path: v3.2.1\n")

    rc, _, stderr = wrapper("init", "align", "-o", str(out))
    assert rc == 1
    assert "already exists" in stderr
    assert out.read_text() == "cactus_path: v3.2.1\n"

    rc, _, stderr = wrapper("init", "align", "-o", str(out), "--force")
    assert rc == 0, stderr
    assert out.read_text() != "cactus_path: v3.2.1\n"


def test_init_rejects_directory(tmp_path):
    rc, _, stderr = wrapper("init", "align", "-o", str(tmp_path))
    assert rc == 1
    assert "is a directory" in stderr

#############################################################################
# version and check

def test_version():
    with open(os.path.join(REPO_ROOT, "lib", "info.yaml")) as f:
        version = yaml.safe_load(f)["version"]
    rc, stdout, _ = wrapper("version")
    assert rc == 0
    assert stdout.strip() == f"cactus-snakemake {version}"


@pytest.mark.skipif(shutil.which("conda") is None, reason="conda is not on PATH")
def test_check_missing_env():
    # Read-only: check never creates or changes an environment
    rc, _, stderr = wrapper("check")
    assert rc == 1
    assert f"Environment '{NO_ENV}' is NOT installed" in stderr
