#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Literal, NoReturn

from ruamel.yaml import YAML

from .pypi import find_dist, get_metadata


class MkpkgFailedException(Exception):
    pass


def run_prettier(meta_path: str | Path) -> None:
    subprocess.run(["npx", "prettier", "-w", meta_path])


def make_package(
    packages_dir: Path,
    package: str,
    version: str | None = None,
    source_fmt: Literal["wheel", "sdist"] | None = None,
) -> None:
    """
    Creates a template that will work for most pure Python packages,
    but will have to be edited for more complex things.
    """
    print(f"Creating meta.yaml package for {package}")

    yaml = YAML()

    pypi_metadata = get_metadata(package, version)

    if source_fmt:
        sources = [source_fmt]
    else:
        # Prefer wheel unless sdist is specifically requested.
        sources = ["wheel", "sdist"]
    dist_metadata = find_dist(pypi_metadata, sources)

    url = dist_metadata["url"]
    sha256 = dist_metadata["digests"]["sha256"]
    version = pypi_metadata["info"]["version"]

    homepage = pypi_metadata["info"]["home_page"]
    summary = pypi_metadata["info"]["summary"]
    license = pypi_metadata["info"]["license"]
    pypi = "https://pypi.org/project/" + package

    yaml_content = {
        "package": {"name": package, "version": version},
        "source": {"url": url, "sha256": sha256},
        "test": {"imports": [package]},
        "about": {
            "home": homepage,
            "PyPI": pypi,
            "summary": summary,
            "license": license,
        },
    }

    package_dir = packages_dir / package
    package_dir.mkdir(parents=True, exist_ok=True)

    meta_path = package_dir / "meta.yaml"
    if meta_path.exists():
        raise MkpkgFailedException(f"The package {package} already exists")

    yaml.dump(yaml_content, meta_path)
    try:
        run_prettier(meta_path)
    except FileNotFoundError:
        warnings.warn("'npx' executable missing, output has not been prettified.")

    success(f"Output written to {meta_path}")


# TODO: use rich for coloring outputs
class bcolors:
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


def abort(msg: str) -> NoReturn:
    print(bcolors.FAIL + msg + bcolors.ENDC)
    sys.exit(1)


def warn(msg: str) -> None:
    warnings.warn(bcolors.WARNING + msg + bcolors.ENDC)


def success(msg: str) -> None:
    print(bcolors.OKBLUE + msg + bcolors.ENDC)


def update_package(
    root: Path,
    package: str,
    version: str | None = None,
    update_patched: bool = True,
    source_fmt: Literal["wheel", "sdist"] | None = None,
) -> None:

    yaml = YAML()

    meta_path = root / package / "meta.yaml"
    if not meta_path.exists():
        abort(f"{meta_path} does not exist")

    yaml_content = yaml.load(meta_path.read_bytes())

    if "url" not in yaml_content["source"]:
        raise MkpkgFailedException(f"Skipping: {package} is a local package!")

    build_info = yaml_content.get("build", {})
    if build_info.get("library", False) or build_info.get("sharedlibrary", False):
        raise MkpkgFailedException(f"Skipping: {package} is a library!")

    if yaml_content["source"]["url"].endswith("whl"):
        old_fmt = "wheel"
    else:
        old_fmt = "sdist"

    pypi_metadata = get_metadata(package, version)
    pypi_ver = pypi_metadata["info"]["version"]
    local_ver = yaml_content["package"]["version"]
    already_up_to_date = pypi_ver <= local_ver and (
        source_fmt is None or source_fmt == old_fmt
    )
    if already_up_to_date:
        print(f"{package} already up to date. Local: {local_ver} PyPI: {pypi_ver}")
        return

    print(f"{package} is out of date: {local_ver} <= {pypi_ver}.")

    if "patches" in yaml_content["source"]:
        if update_patched:
            warn(
                f"Pyodide applies patches to {package}. Update the "
                "patches (if needed) to avoid build failing."
            )
        else:
            raise MkpkgFailedException(
                f"Pyodide applies patches to {package}. Skipping update."
            )

    if source_fmt:
        # require the type requested
        sources = [source_fmt]
    elif old_fmt == "wheel":
        # prefer wheel to sdist
        sources = ["wheel", "sdist"]
    else:
        # prefer sdist to wheel
        sources = ["sdist", "wheel"]

    dist_metadata = find_dist(pypi_metadata, sources)

    yaml_content["source"]["url"] = dist_metadata["url"]
    yaml_content["source"].pop("md5", None)
    yaml_content["source"]["sha256"] = dist_metadata["digests"]["sha256"]
    yaml_content["package"]["version"] = pypi_metadata["info"]["version"]

    yaml.dump(yaml_content, meta_path)
    run_prettier(meta_path)

    success(f"Updated {package} from {local_ver} to {pypi_ver}.")


def make_parser(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    parser.description = """
Make a new pyodide package. Creates a simple template that will work
for most pure Python packages, but will have to be edited for more
complex things.""".strip()
    parser.add_argument("package", type=str, nargs=1, help="The package name on PyPI")
    parser.add_argument("--update", action="store_true", help="Update existing package")
    parser.add_argument(
        "--update-if-not-patched",
        action="store_true",
        help="Update existing package if it has no patches",
    )
    parser.add_argument(
        "--source-format",
        help="Which source format is preferred. Options are wheel or sdist. "
        "If none is provided, then either a wheel or an sdist will be used. "
        "When updating a package, the type will be kept the same if possible.",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Package version string, "
        "e.g. v1.2.1 (defaults to latest stable release)",
    )
    return parser


def main(args: argparse.Namespace) -> None:
    PYODIDE_ROOT = os.environ.get("PYODIDE_ROOT")
    if PYODIDE_ROOT is None:
        raise ValueError("PYODIDE_ROOT is not set")

    PACKAGES_ROOT = Path(PYODIDE_ROOT) / "packages"

    try:
        package = args.package[0]
        if args.update:
            update_package(
                PACKAGES_ROOT,
                package,
                args.version,
                update_patched=True,
                source_fmt=args.source_format,
            )
            return
        if args.update_if_not_patched:
            update_package(
                PACKAGES_ROOT,
                package,
                args.version,
                update_patched=False,
                source_fmt=args.source_format,
            )
            return
        make_package(
            PACKAGES_ROOT, package, args.version, source_fmt=args.source_format
        )
    except MkpkgFailedException as e:
        # This produces two types of error messages:
        #
        # When the request to get the pypi json fails, it produces a message like:
        # "Failed to load metadata for libxslt from https://pypi.org/pypi/libxslt/json: HTTP Error 404: Not Found"
        #
        # If there is no sdist it prints an error message like:
        # "No sdist URL found for package swiglpk (https://pypi.org/project/swiglpk/)"
        abort(e.args[0])


if __name__ == "__main__":
    parser = make_parser(argparse.ArgumentParser())
    args = parser.parse_args()
    main(args)
