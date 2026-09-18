"""Enforces that workload and target code never import third-party modules.

The target interpreter runs with no packages installed. An accidental
dependency would only surface as a CI failure on one interpreter, so it is
checked here instead.
"""

import pathlib
import subprocess
import sys

PURE_PACKAGES = ("bench.workloads", "bench.target")
SRC = pathlib.Path(__file__).parent.parent / "src"


def _modules_under(package: str) -> list[str]:
    directory = SRC / package.replace(".", "/")
    return [
        f"{package}.{path.stem}"
        for path in sorted(directory.glob("*.py"))
        if path.stem != "__init__"
    ]


def test_pure_modules_import_without_site_packages() -> None:
    modules = [name for package in PURE_PACKAGES for name in _modules_under(package)]
    assert modules, "no modules discovered; check the directory layout"
    # -I implies -E, which makes the interpreter ignore PYTHONPATH entirely,
    # so the source directory is added to sys.path from within the program
    # instead of via the environment.
    program = f"import sys; sys.path.insert(0, {str(SRC)!r})\nimport importlib\n" + "".join(
        f"importlib.import_module({name!r})\n" for name in modules
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-S", "-c", program],
        env={},
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
