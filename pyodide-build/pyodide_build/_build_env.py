import os
import sys
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path

from .common import search_pyodide_root


def init_environment(*, quiet: bool = False) -> None:
    """
    Initialize Pyodide build environment.
    This function needs to be called before any other Pyodide build functions.
    """
    if os.environ.get("__LOADED_PYODIDE_ENV"):
        return

    os.environ["__LOADED_PYODIDE_ENV"] = "1"

    _set_pyodide_root(quiet=quiet)


def _set_pyodide_root(*, quiet: bool = False) -> None:
    """
    Initialize Pyodide build environment, namely set PYODIDE_ROOT environment variable.
    This function works both in-tree and out-of-tree builds:
    - In-tree builds: Searches for the root of the Pyodide repository in parent directories
    - Out-of-tree builds: Downloads and installs the Pyodide build environment into the current directory
    Parameters
    ----------
    quiet
        If True, do not print any messages
    """

    from . import install_xbuildenv  # avoid circular import

    # If we are building docs, we don't need to know the PYODIDE_ROOT
    if "sphinx" in sys.modules:
        os.environ["PYODIDE_ROOT"] = ""
        return

    # 1) If PYODIDE_ROOT is already set, do nothing
    if "PYODIDE_ROOT" in os.environ:
        return

    # 2) If we are doing an in-tree build,
    #    set PYODIDE_ROOT to the root of the Pyodide repository
    try:
        os.environ["PYODIDE_ROOT"] = str(search_pyodide_root(Path.cwd()))
        return
    except FileNotFoundError:
        pass

    # 3) If we are doing an out-of-tree build,
    #    download and install the Pyodide build environment
    xbuildenv_path = Path(".pyodide-xbuildenv").resolve()

    if xbuildenv_path.exists():
        os.environ["PYODIDE_ROOT"] = str(xbuildenv_path / "xbuildenv" / "pyodide-root")
        return

    with ExitStack() as stack:
        if quiet:
            # Prevent writes to stdout
            stack.enter_context(redirect_stdout(StringIO()))

        # install_xbuildenv will set PYODIDE_ROOT env variable, so we don't need to do it here
        # TODO: return the path to the xbuildenv instead of setting the env variable inside install_xbuildenv
        install_xbuildenv.install(xbuildenv_path, download=True)

    # TODO: move following code to `get_build_environment_vars` function
    from .common import get_hostsitepackages, get_make_environment_vars

    os.environ.update(get_make_environment_vars())
    try:
        hostsitepackages = get_hostsitepackages()
        pythonpath = [
            hostsitepackages,
        ]
        os.environ["PYTHONPATH"] = ":".join(pythonpath)
    except KeyError:
        pass
    os.environ["BASH_ENV"] = ""
