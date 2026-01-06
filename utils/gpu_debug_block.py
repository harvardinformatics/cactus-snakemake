## # GPU diagnostics for Slurm + Singularity jobs
## Add this code snippet to the top of any GPU-using rule's run: blocks to
## capture host and container GPU visibility information to the job log.
## This helps debug whether Slurm/singularity exposed GPUs to the job.
##
        sif = params.path
        # Write some host-level diagnostics to the job log first so we can see what
        # the compute node and Slurm environment provided to the job before
        # invoking the container. This helps debug whether Slurm/singularity
        # exposed both GPUs to the job.
        try:
            with open(log.job_log, "w") as _lf:
                # hostname
                try:
                    _hf = subprocess.run(["hostname"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
                    _lf.write("HOSTNAME:\n" + _hf.stdout + "\n")
                except Exception:
                    pass

                # SLURM environment variables
                try:
                    _env = subprocess.run(["env"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
                    slurm_lines = [l for l in _env.stdout.splitlines() if l.startswith("SLURM_")]
                    _lf.write("SLURM ENV:\n" + "\n".join(slurm_lines) + "\n\n")
                except Exception:
                    pass

                # Capture process ancestry and parent commandline to reveal exact srun/sbatch invocation
                try:
                    _lf.write("PROCESS DIAGNOSTICS:\n")
                    mypid = os.getpid()
                    _lf.write(f"THIS_PID: {mypid}\n")

                    # Walk ancestors and record ps output for each
                    cur = mypid
                    _lf.write("ANCESTOR_PS_LINES:\n")
                    while cur and cur != 1:
                        try:
                            _ps = subprocess.run(["ps", "-o", "pid,ppid,user,cmd", "--no-headers", "-p", str(cur)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
                            _lf.write(_ps.stdout + "\n")
                            parts = _ps.stdout.split()
                            if len(parts) >= 2:
                                ppid = parts[1]
                                if ppid in ("0", "1"):
                                    break
                                cur = int(ppid)
                            else:
                                break
                        except Exception:
                            break

                    # Parent cmdline from /proc (may show exact srun invocation)
                    try:
                        ppid = os.getppid()
                        with open(f"/proc/{ppid}/cmdline", "r") as _cf:
                            _cmd = _cf.read().replace('\0', ' ').strip()
                        _lf.write(f"PARENT_CMDLINE(/proc/{ppid}/cmdline): {_cmd}\n")
                    except Exception:
                        _lf.write("PARENT_CMDLINE: unavailable\n")

                    # If available, call scontrol to dump job/step metadata
                    try:
                        if os.environ.get("SLURM_JOB_ID"):
                            _jc = subprocess.run(["scontrol", "show", "job", os.environ.get("SLURM_JOB_ID")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
                            _lf.write("SCONTROL JOB SHOW:\n" + _jc.stdout + "\n")
                    except Exception:
                        pass

                    try:
                        if os.environ.get("SLURM_STEP_ID"):
                            _sc = subprocess.run(["scontrol", "show", "step", os.environ.get("SLURM_STEP_ID")], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
                            _lf.write("SCONTROL STEP SHOW:\n" + _sc.stdout + "\n")
                    except Exception:
                        pass
                except Exception:
                    # Never fail the job because diagnostics failed
                    pass

                # Host nvidia-smi (if available on the node)
                try:
                    _nv = subprocess.run(["nvidia-smi", "-L"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
                    _lf.write("HOST NVIDIA-SMI -L:\n" + _nv.stdout + "\n")
                except FileNotFoundError:
                    _lf.write("nvidia-smi not found on host PATH\n")
                except subprocess.CalledProcessError:
                    _lf.write("nvidia-smi returned non-zero on host\n")
        except Exception:
            CLOG.debug("Unable to write initial host diagnostics to job log")

        if sif:
            try:
                # Probe NVIDIA devices inside the container and append to the same log
                with open(log.job_log, "a") as _lf:
                    try:
                        subprocess.check_call(["singularity", "exec", "--nv", sif, "nvidia-smi", "-L"], stdout=_lf, stderr=subprocess.STDOUT)
                    except subprocess.CalledProcessError as e:
                        CLOG.warning(f"nvidia-smi in singularity returned non-zero exit status: {e.returncode}")
                    except FileNotFoundError:
                        CLOG.warning("singularity not found in PATH; skipping GPU probe")

                    # Dump CUDA_VISIBLE_DEVICES from inside the container
                    try:
                        proc = subprocess.run(
                            ["singularity", "exec", "--nv", sif, "bash", "-lc", "echo CUDA_VISIBLE_DEVICES=\$CUDA_VISIBLE_DEVICES; env"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            check=True
                        )
                        matches = [line for line in proc.stdout.splitlines() if re.search(r"CUDA_VISIBLE_DEVICES|CUDA_VISIBLE_DEVICE", line, re.I)]
                        if matches:
                            _lf.write("\nCONTAINER CUDA/VISIBILITY:\n" + "\n".join(matches) + "\n")
                        else:
                            CLOG.debug("CUDA_VISIBLE_DEVICES not found in container env")
                    except subprocess.CalledProcessError as e:
                        CLOG.warning(f"singularity env probe returned non-zero exit status: {e.returncode}")
                    except FileNotFoundError:
                        CLOG.warning("singularity not found in PATH; skipping container env probe")
            except Exception:
                CLOG.debug("Failed probing container GPU environment")
        else:
            CLOG.debug("No 'singularity_sif' set in config; skipping GPU env probe")