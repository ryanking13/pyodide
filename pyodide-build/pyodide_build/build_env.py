from functools import cache
from pathlib import Path

from .common import environment_substitute_args


@cache
def _get_package_build_config_base() -> dict[str, str]:
    tools_dir = Path(__file__).parent / "tools"

    build_config: dict[str, str] = {
        "PYODIDE": "1",
        # This is the legacy environment variable used for the aforementioned purpose
        "PYODIDE_PACKAGE_ABI": "1",
        # A directory containing the built libraries.
        "WASM_LIBRARY_DIR": "$(PYODIDE_ROOT)/packages/.libs",
        "PKG_CONFIG_PATH": "$(PYODIDE_ROOT)/packages/.libs/lib/pkgconfig",
        # A directory containing the Python packages that are used during the cross compilation.
        "HOSTINSTALLDIR": "$(PYODIDE_ROOT)/packages/.artifacts",
        "HOSTSITEPACKAGES": "$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages",
        "NUMPY_LIB": "$(PYODIDE_ROOT)/packages/.artifacts/lib/python$(PYMAJOR).$(PYMINOR)/site-packages/numpy",
        # Build flags
        "SIDE_MODULE_LDFLAGS": "$(LDFLAGS_BASE) -s SIDE_MODULE=1",
        "SIDE_MODULE_CXXFLAGS": "$(CXXFLAGS_BASE)",
        "SIDE_MODULE_CFLAGS": "$(CFLAGS_BASE) -I$(PYTHONINCLUDE)",
        "STDLIB_MODULE_CFLAGS": "$(CFLAGS_BASE) -I Include/ -I . -I Include/internal/",
        # For Rust
        "CARGO_BUILD_TARGET": "wasm32-unknown-emscripten",
        "CARGO_TARGET_WASM32_UNKNOWN_EMSCRIPTEN_LINKER": "emcc",
        "RUST_TOOLCHAIN": "nightly-2023-04-29",
        "PYO3_CROSS_LIB_DIR": "$(CPYTHONINSTALL)/lib",
        "PYO3_CROSS_INCLUDE_DIR": "$(PYTHONINCLUDE)",
        "PYO3_CONFIG_FILE": str(tools_dir / "pyo3_config.ini"),
        # idealy we could automatically include all SIDE_MODULE_LDFLAGS here
        "RUSTFLAGS": "-C link-arg=-sSIDE_MODULE=2 -C link-arg=-sWASM_BIGINT -Z link-native-libraries=no",
        # For CMake
        "CMAKE_TOOLCHAIN_FILE": str(
            tools_dir / "cmake/Modules/Platform/Emscripten.cmake"
        ),
    }

    build_config["PYTHONPATH"] = build_config["HOSTSITEPACKAGES"]

    return build_config


def get_package_build_config(env: dict[str, str]) -> dict[str, str]:
    """
    Get the build configuration for a package.

    Parameters
    ----------
    env:
        The host environment variables. This is used for environment variable substitution.

    Returns
    -------
    The build configuration for the package.
    """

    build_config_base = _get_package_build_config_base()
    build_config = environment_substitute_args(build_config_base, env)

    return build_config


def dump_config(config: dict[str, str]) -> str:
    """
    Dump the build configuration for a package into a TOML format.

    Parameters
    ----------
    config
        The build configuration for the package build.
    """
    import tomli_w

    # Dumps config under [tool.pyodide] section, so that it can be written to pyproject.toml
    # This is not used yet, but for future compatibility
    _config = {"tool": {"pyodide": config}}

    return tomli_w.dumps(config)
