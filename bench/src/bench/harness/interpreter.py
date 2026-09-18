"""Installation and resolution of target interpreters through uv."""

import subprocess

import structlog

INSTALL_TIMEOUT_S = 300.0

log = structlog.get_logger(__name__)


class InterpreterInstallFailedError(Exception):
    """Raised when uv could not provide the requested interpreter."""


def install_interpreter(python_key: str, *, uv_executable: str = "uv") -> str:
    """Install a target interpreter and return the path to its executable.

    `--managed-python` is passed explicitly because `UV_NO_MANAGED_PYTHON` in
    the ambient environment would otherwise make uv silently refuse to
    download anything.

    Args:
        python_key: Full uv interpreter key to install.
        uv_executable: Path to the uv binary.

    Returns:
        Absolute path to the installed interpreter.

    Raises:
        InterpreterInstallFailedError: If uv could not install or locate it.
    """
    try:
        subprocess.run(
            [uv_executable, "python", "install", "--managed-python", python_key],
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT_S,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise InterpreterInstallFailedError(
            f"uv could not install {python_key}: {error}"
        ) from error

    try:
        located = subprocess.run(
            [uv_executable, "python", "find", "--managed-python", python_key],
            capture_output=True,
            text=True,
            timeout=INSTALL_TIMEOUT_S,
            check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as error:
        raise InterpreterInstallFailedError(
            f"uv installed {python_key} but could not locate it: {error}"
        ) from error

    path = located.stdout.strip()
    if path == "":
        raise InterpreterInstallFailedError(f"uv returned no path for {python_key}")
    log.info("interpreter.installed", extra={"python_key": python_key, "path": path})
    return path
