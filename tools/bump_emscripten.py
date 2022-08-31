#!/usr/bin/env python
import json
import re
import urllib.request
from pathlib import Path


def get_latest_emsdk_tag():
    resp = urllib.request.urlopen(
        "https://api.github.com/repos/emscripten-core/emsdk/tags"
    )

    if resp.getcode() != 200:
        raise RuntimeError("Failed to get emsdk tags")

    tags = json.loads(resp.read())
    latest_tag = tags[0]

    return latest_tag["name"]


def get_current_emsdk_tag():
    build_env = (Path(__file__).parent.parent / "Makefile.envs").read_text()
    match = re.search(r"PYODIDE_EMSCRIPTEN_VERSION\s+\?=\s+(.*)", build_env)

    if not match:
        raise RuntimeError("Could not find current emsdk tag")

    tag = match[1]
    return tag


def bump_emsdk_tag(current_tag, new_tag):
    build_env = (Path(__file__).parent.parent / "Makefile.envs").read_text()
    build_env = build_env.replace(current_tag, new_tag)
    (Path(__file__).parent.parent / "Makefile.envs").write_text(build_env)

    print(f"Bumped emsdk tags from {current_tag} to {new_tag}")


def main():
    current_tag = get_current_emsdk_tag()
    latest_tag = get_latest_emsdk_tag()

    if current_tag == latest_tag:
        print("Emsdk tags are up to date")
        exit(1)

    bump_emsdk_tag(current_tag, latest_tag)


if __name__ == "__main__":
    main()
