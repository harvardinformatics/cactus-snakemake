#!/usr/bin/env python3
"""
check_env_updates.py

Checks every dependency in envs/environment.yml (both the top-level conda list
and the pip: section) for a newer available version, prompts interactively per
package, and writes approved bumps back into environment.yml as version pins.

Does NOT apply the update itself - cactus_snakemake's existing hash-based
staleness check picks up the file change and runs the real env update the next
time 'setup' is run.

Copied from phyloacc-workflows (utils/check_env_updates.py); only the wrapper
name in messages differs.

Uses the target env's own interpreter (sys.executable) for every pip call
rather than a bare "pip" - conda activate has repeatedly not reliably reordered
$PATH in this environment, so this sidesteps that entirely.

For conda-managed packages, "latest available version" comes from each
channel's channeldata.json (https://conda.anaconda.org/<channel>/channeldata.json)
rather than `mamba/conda search <pkg>` - the latter has to parse the full
channel index from scratch on every process invocation (~15-30s per package,
confirmed directly - conda-forge/bioconda are already the only channels
configured, so it's not extra-channel searching, just inherent per-call
overhead), whereas channeldata.json is one small aggregate file per channel,
fetched once for the whole dependency list (~1s total). Channels are checked
in the order listed in environment.yml's own `channels:`, first match wins,
matching `channel_priority: strict` semantics rather than blindly taking the
max version across channels.

Usage: python3 check_env_updates.py <environment.yml> <env_name> [--dry-run]
"""

import json
import re
import subprocess
import sys
import urllib.request

import yaml

CONSTRAINT_RE = re.compile(r"^([A-Za-z0-9_.\-]+)\s*(.*)$")
UPPER_BOUND_RE = re.compile(r"<\s*([0-9][0-9A-Za-z.]*)")
LOWER_BOUND_RE = re.compile(r">=\s*([0-9][0-9A-Za-z.]*)")


def version_key(v):
    return tuple(int(x) for x in re.findall(r"\d+", v))


def parse_entry(entry):
    # "python>=3.11,<3.13" -> name="python", constraint=">=3.11,<3.13"
    m = CONSTRAINT_RE.match(entry.strip())
    name = m.group(1)
    constraint = m.group(2).strip()
    upper = UPPER_BOUND_RE.search(constraint)
    upper_bound = upper.group(1) if upper else None
    return name, constraint, upper_bound


def conda_installed_version(env_name, pkg):
    result = subprocess.run(
        ["conda", "list", "-n", env_name, pkg, "--json"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    for entry in data:
        if entry.get("name") == pkg:
            return entry.get("version")
    return None


def fetch_channeldata(channel):
    url = f"https://conda.anaconda.org/{channel}/channeldata.json"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            data = json.load(resp)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[check_env_updates] warning: could not fetch channeldata for '{channel}': {e}", file=sys.stderr)
        return {}
    return data.get("packages", {})


def conda_latest_version(pkg, upper_bound, channel_data_by_channel, channel_order):
    # First channel (in environment.yml's own declared order) that has this
    # package wins - matches channel_priority: strict, not "max across channels".
    # channeldata.json only exposes ONE aggregate "latest" version per package,
    # not a full version list - if that single known version exceeds an
    # existing upper-bound cap, there's no way to tell from this data source
    # alone whether some in-range version newer than what's installed exists.
    # Returns (latest_within_cap_or_None, raw_version_if_capped_out_or_None).
    for channel in channel_order:
        pkgs = channel_data_by_channel.get(channel, {})
        info = pkgs.get(pkg)
        if info is None:
            continue
        version = info.get("version")
        if version is None:
            continue
        if upper_bound is not None and version_key(version) >= version_key(upper_bound):
            return None, version
        return version, None
    return None, None


def pip_versions(pkg):
    # mafutils (0.3.0)
    # Available versions: 0.3.0, 0.2.1, 0.2.0, 0.1.1
    #   INSTALLED: 0.1.1
    #   LATEST:    0.3.0
    result = subprocess.run(
        [sys.executable, "-m", "pip", "index", "versions", pkg],
        capture_output=True, text=True,
    )
    output = result.stdout + result.stderr
    installed_m = re.search(r"INSTALLED:\s*(\S+)", output)
    latest_m = re.search(r"LATEST:\s*(\S+)", output)
    if installed_m and latest_m:
        return installed_m.group(1), latest_m.group(1)
    # No INSTALLED/LATEST breakdown shown when already at the newest version -
    # fall back to pip show for the installed version in that case.
    header_m = re.search(rf"^{re.escape(pkg)}\s*\(([^)]+)\)", output, re.MULTILINE)
    if not header_m:
        return None, None
    latest = header_m.group(1)
    show = subprocess.run(
        [sys.executable, "-m", "pip", "show", pkg],
        capture_output=True, text=True,
    )
    show_m = re.search(r"^Version:\s*(\S+)", show.stdout, re.MULTILINE)
    installed = show_m.group(1) if show_m else latest
    return installed, latest


def main():
    args = sys.argv[1:]
    dry_run_flags = {"--dry-run", "--dryrun"}
    dry_run = any(a in dry_run_flags for a in args)
    positional = [a for a in args if a not in dry_run_flags]

    if len(positional) != 2:
        print(f"Usage: {sys.argv[0]} <environment.yml> <env_name> [--dry-run|--dryrun]", file=sys.stderr)
        sys.exit(1)

    env_file, env_name = positional

    with open(env_file) as f:
        env_yaml = yaml.safe_load(f)

    conda_deps = []
    pip_deps = []
    for entry in env_yaml.get("dependencies", []):
        if isinstance(entry, dict) and "pip" in entry:
            pip_deps.extend(entry["pip"])
        elif isinstance(entry, str):
            conda_deps.append(entry)

    channel_order = [c for c in env_yaml.get("channels", []) if c != "nodefaults"]

    print(f"[check_env_updates] Checking {len(conda_deps)} conda package(s) and "
          f"{len(pip_deps)} pip package(s) against env '{env_name}' ...")
    print(f"[check_env_updates] Fetching channeldata for {', '.join(channel_order)} ...", flush=True)
    channel_data_by_channel = {c: fetch_channeldata(c) for c in channel_order}

    candidates = []  # (name, source, entry, constraint, upper_bound, installed, latest)

    for entry in conda_deps:
        name, constraint, upper_bound = parse_entry(entry)
        if name == "pip":
            continue
        print(f"[check_env_updates]   checking {name} ...", end="", flush=True)
        installed = conda_installed_version(env_name, name)
        if installed is None:
            print(" not found in env, skipping", file=sys.stderr)
            continue
        latest, capped_raw = conda_latest_version(name, upper_bound, channel_data_by_channel, channel_order)
        if latest is None:
            if capped_raw is not None:
                print(f" latest known ({capped_raw}) exceeds the existing cap (<{upper_bound}) - "
                      f"can't tell if a newer in-range version exists, skipping", flush=True)
            else:
                print(" not found in any configured channel, skipping", file=sys.stderr)
            continue
        if version_key(latest) > version_key(installed):
            print(f" {installed} -> {latest} available", flush=True)
            candidates.append((name, "conda", entry, constraint, upper_bound, installed, latest))
        else:
            print(f" already current ({installed})", flush=True)

    for entry in pip_deps:
        name, constraint, upper_bound = parse_entry(entry)
        print(f"[check_env_updates]   checking {name} ...", end="", flush=True)
        installed, latest = pip_versions(name)
        if installed is None or latest is None:
            print(" could not determine versions, skipping", file=sys.stderr)
            continue
        if version_key(latest) > version_key(installed):
            print(f" {installed} -> {latest} available", flush=True)
            candidates.append((name, "pip", entry, constraint, upper_bound, installed, latest))
        else:
            print(f" already current ({installed})", flush=True)

    if not candidates:
        print("[check_env_updates] Everything is already at its latest available version.")
        return

    if dry_run:
        print(f"[check_env_updates] {len(candidates)} update(s) available (dry run - "
              "nothing prompted or written):")
        for name, source, entry, constraint, upper_bound, installed, latest in candidates:
            print(f"[check_env_updates]   {name}: {installed} -> {latest} ({source})")
        return

    with open(env_file) as f:
        lines = f.readlines()

    changed = []
    for name, source, entry, constraint, upper_bound, installed, latest in candidates:
        answer = input(f"[check_env_updates] Update {name} from {installed} to {latest} ({source})? [y/N] ").strip().lower()
        if answer != "y":
            continue

        if LOWER_BOUND_RE.search(constraint):
            new_entry = LOWER_BOUND_RE.sub(f">={latest}", entry, count=1)
        elif constraint:
            new_entry = f"{name}>={latest},{constraint}"
        else:
            new_entry = f"{name}>={latest}"

        for i, line in enumerate(lines):
            lstripped = line.lstrip()
            if not lstripped.startswith("-"):
                continue
            after_dash = lstripped[1:].lstrip()
            # startswith, not ==, so this also matches lines with a trailing
            # inline comment (e.g. python's cap-rationale comment) - only the
            # entry substring itself gets replaced, comment stays untouched.
            if after_dash.startswith(entry.strip()):
                lines[i] = line.replace(entry.strip(), new_entry, 1)
                break
        changed.append((name, entry.strip(), new_entry))

    if not changed:
        print("[check_env_updates] No changes made.")
        return

    with open(env_file, "w") as f:
        f.writelines(lines)

    print(f"[check_env_updates] Updated {env_file}:")
    for name, old, new in changed:
        print(f"[check_env_updates]   {name}: {old} -> {new}")
    print("[check_env_updates] Run 'cactus_snakemake setup' to apply these changes to the environment.")


if __name__ == "__main__":
    main()
