#!/usr/bin/env bash

failure_exit() {
  echo >&2 "Could not find ${1}.  Please install that before continuing."
  exit 1
}

check_python_version() {
  if ! command -v python"$PYMAJOR"."$PYMINOR" &> /dev/null; then
    echo >&2 "Must compile with python $PYMAJOR.$PYMINOR."
    exit 1
  fi
}

check_binary_present() {
  local binary_exists
  binary_exists="$(command -v "${1}")"
  if [ ! "${binary_exists}" ]; then
    failure_exit "${1}"
  fi
}

check_build_deps() {
  check_binary_present "make"
  check_binary_present "cmake"
  check_binary_present "git"
  check_binary_present "shasum"
  check_binary_present "pkg-config"
}

check_non_gnu_binaries() {
  check_binary_present "patch"
  check_binary_present "sed"

  if ! patch --version | grep -q "GNU patch"; then
    echo >&2 "It seems like you are not using GNU patch, if you are building in MacOS, try installing 'gpatch'"
    exit 1
  fi

  if ! sed --version | grep -q "GNU sed"; then
    echo >&2 "It seems like you are not using GNU sed, if you are building in MacOS, try installing 'gnu-sed'"
    exit 1
  fi
}

check_python_version
check_build_deps
check_non_gnu_binaries
