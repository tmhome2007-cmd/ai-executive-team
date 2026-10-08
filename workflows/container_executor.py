"""Constrained Docker command executor.

The model controls only the shell script executed *inside* the worker.
It never controls Docker flags, mounts, image, user, network or capabilities.
Docker must be locally installed and the configured image pre-pulled.
Never mount the Docker socket into this worker.
"""
import os
from pathlib import Path
import shutil
import secrets
import subprocess

WORKER_IMAGE = "alpine:3.20"
MAX_OUTPUT_BYTES = 65536


class ContainerExecutionError(RuntimeError):
    pass


def run_in_container(command: str, workspace_root: str) -> subprocess.CompletedProcess[str]:
    if not isinstance(command, str) or not command.strip():
        raise ContainerExecutionError("Empty command rejected")
    root = Path(workspace_root).resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ContainerExecutionError("Invalid workspace directory")
    if not hasattr(os, "getuid") or os.getuid() == 0:
        raise ContainerExecutionError("Requires non-root Unix host identity")
    docker = shutil.which("docker")
    if not docker:
        raise ContainerExecutionError("Docker unavailable: fail closed")
    container_name = "executive-worker-" + secrets.token_hex(12)
    args = [
        docker, "run", "--rm", "--name", container_name, "--pull=never",
        "--network=none", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=64", "--memory=256m", "--cpus=1",
        f"--user={os.getuid()}:{os.getgid()}",
        "--mount", f"type=bind,source={root},target=/workspace",
        "--workdir=/workspace",
        "--tmpfs=/tmp:rw,noexec,nosuid,size=16m",
        WORKER_IMAGE, "/bin/sh", "-c", command,
    ]
    try:
        result = subprocess.run(
            args, shell=False, text=True, capture_output=True,
            timeout=30, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        # Killing the Docker CLI does not always kill the container in the daemon.
        try:
            subprocess.run([docker, "rm", "-f", container_name], shell=False,
                           capture_output=True, timeout=10, check=False)
        except (OSError, subprocess.TimeoutExpired):
            pass
        raise ContainerExecutionError("Container timed out; attempted forced cleanup") from exc
    except OSError as exc:
        raise ContainerExecutionError("Container invocation failed") from exc
    # Fail closed on unexpectedly large output instead of recording it.
    if len(result.stdout.encode("utf-8")) + len(result.stderr.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise ContainerExecutionError("Container output exceeded bounded result size")
    return result
