"""
Builders for out-of-tree package builds.
"""
from abc import ABC, abstractmethod
import os
from pathlib import Path
import tempfile
from urllib.parse import urlparse
import shutil

import requests

from .. import build_env, common, pypabuild
from ..io import _BuildSpecExports
from .pypi import fetch_pypi_package


class Builder(ABC):
    """
    Base class for builders, which implements the common logic for all builders.
    Builders which inherit from this class should implement the following methods:
    - prepare()
    - build()
    - cleanup()
    """
    def __init__(self, pkg: str, outdir: Path, exports: _BuildSpecExports, backend_flags: list[str]):
        """
        Parameters
        ----------
        pkg
            Query string for the package to build.
            This can be a URL, a path to a local folder, or a PyPI package name.
            
        outdir
            Path to the output directory.
            The built wheel will be placed in this directory.

        exports
            Which symbols should be exported from the built shared libraries.

        backend_flags
            Extra arguments to pass to the build backend.
        """
        self.pkg = pkg
        self.outdir = outdir
        self.exports = exports
        self.backend_flags = backend_flags
    
    @abstractmethod
    def prepare(self):
        """
        Prepare the build environment.
        e.g. download source code, etc.
        """
        ...

    @abstractmethod
    def build(self) -> Path:
        """
        Build the package. This is the main entry point for the builder.
        """
        ...
    
    @abstractmethod
    def cleanup(self):
        """
        Cleanup the build environment.
        """
        ...

    def run(
        self,
        pkgdir: Path,
    ) -> Path:
        """
        Build the package from source using pypabuild.

        Parameters
        ----------
        pkgdir
            Path to the source directory. This directory should be the base directory
            of the package where normally pyproject.toml or setup.py is located.

        Returns
        -------
        Path
            Path to the built wheel.
        """
        self.prepare()

        outdir = self.outdir.resolve()
        outdir.mkdir(parents=True, exist_ok=True)

        cflags = build_env.get_build_flag("SIDE_MODULE_CFLAGS")
        cflags += f" {os.environ.get('CFLAGS', '')}"
        cxxflags = build_env.get_build_flag("SIDE_MODULE_CXXFLAGS")
        cxxflags += f" {os.environ.get('CXXFLAGS', '')}"
        ldflags = build_env.get_build_flag("SIDE_MODULE_LDFLAGS")
        ldflags += f" {os.environ.get('LDFLAGS', '')}"
        target_install_dir = os.environ.get(
            "TARGETINSTALLDIR", build_env.get_build_flag("TARGETINSTALLDIR")
        )

        env = os.environ.copy()
        env.update(build_env.get_build_environment_vars())

        build_env_ctx = pypabuild.get_build_env(
            env=env,
            pkgname="",
            cflags=cflags,
            cxxflags=cxxflags,
            ldflags=ldflags,
            target_install_dir=target_install_dir,
            exports=self.exports,
        )

        with build_env_ctx as env:
            built_wheel = pypabuild.build(pkgdir, outdir, env, " ".join(self.backend_flags))

        wheel_path = Path(built_wheel)
        with common.modify_wheel(wheel_path) as wheel_dir:
            build_env.replace_so_abi_tags(wheel_dir)

        return wheel_path


class SourceBuilder(Builder):
    """
    Builder for building from a local folder.
    """
    def __init__(self, pkg: str, outdir: Path, exports: _BuildSpecExports, backend_flags: list[str]):
        super().__init__(pkg, outdir, exports, backend_flags)
    
    def prepare(self):
        pass

    def build(self):
        self.run(self.pkg)
    
    def cleanup(self):
        pass


class URLBuilder(Builder):
    """
    Builder for building from a URL.
    """
    def __init__(self, pkg: str, outdir: Path, exports: _BuildSpecExports, backend_flags: list[str]):
        super().__init__(pkg, outdir, exports, backend_flags)

        self._tmpdir: tempfile.TemporaryDirectory | None = None
        self._builddir: Path | None = None
        self._archive_path: Path | None
    
    def prepare(self):
        """
        Download the source code from the given URL.
        """
        self._tmpdir = tempfile.TemporaryDirectory()
        self._builddir = Path(self._tmpdir.name) / "build"
        self._archive_path = self._download_from_url(self.pkg, self.tmpdir)
    
    def build(self) -> Path:
        if self._tmpdir is None or self._builddir is None:
            raise RuntimeError("prepare() must be called before build()")

        # If the source is a wheel, no more work is needed.
        # TODO: check if the wheel is compatible with the WASM platform.
        if self._archive_path.suffix == ".whl":
            dest = self.outdir / self._archive_path.name
            shutil.move(self._archive_path, dest)
            return dest

        # If the source is a source distribution, build it.
        shutil.unpack_archive(self._archive_path, self.builddir)

        files = list(builddir.iterdir())
        if len(files) == 1 and files[0].is_dir():
            # unzipped into subfolder
            builddir = files[0]

        return self.run(builddir)
            
    def cleanup(self):
        if self._tmpdir:
            self._tmpdir.cleanup()

    def _download_from_url(self, url: str, output_directory: Path) -> Path:
        """
        Download the given URL to the given directory.

        Parameters
        ----------
        url
            URL to download from.
        output_directory
            Directory to download to.
        
        Returns
        -------
        Path
            Path to the downloaded file.
        """
        try:
            resp = requests.get(url, stream=True) 
        except Exception as e:
            raise RuntimeError(f"Couldn't download from {url}") from e
    
        urlpath = Path(urlparse(resp.url).path)
        file_name = urlpath.name
        full_path = output_directory / file_name

        with open(full_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1 << 20):
                f.write(chunk)

        return full_path


class PyPIBuilder(Builder):
    """
    Builder for building from PyPI.
    """
    def __init__(self, pkg: Path, outdir: Path, exports: _BuildSpecExports, backend_flags: list[str]):
        super().__init__(pkg, outdir, exports, backend_flags)

        self._tmpdir: tempfile.TemporaryDirectory | None = None
        self._builddir: Path | None = None
        self._package_path: Path | None = None
    
    def prepare(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        # TODO: unpack should be done outside of fetch_pypi_package
        self._package_path = fetch_pypi_package(self.pkg, self.tmpdir)

    def build(self) -> Path:
        if self._tmpdir is None or self._package_path is None:
            raise RuntimeError("prepare() must be called before build()")
    
        if not self._package_path.is_dir():
            # a pure-python wheel has been downloaded - just copy to dist folder
            dest = self.outdir / self.package_path.name
            shutil.copyfile(self.package_path, dest)
            print(f"Successfully fetched: {self.package_path.name}")
            return dest

        return self.run(self.package_path)

    def cleanup(self):
        if self._tmpdir:
            self._tmpdir.cleanup()


def find_builder(pkg: str, outdir: Path, exports: _BuildSpecExports, backend_flags: list[str]) -> Builder:
    """
    Find the appropriate builder for the given package.
    """
    builder = None
    
    if pkg.startswith(("http://", "https://")):  # Build from a URL
        builder = URLBuilder
    elif Path(pkg).resolve().is_dir():  # Most common case, build from a local folder
        builder = SourceBuilder
    elif "/" not in pkg:  # Assume it's a PyPI package
        builder = PyPIBuilder
    else:
        raise RuntimeError(f"Couldn't determine source type for {pkg}")

    return builder(pkg, outdir, exports, backend_flags)