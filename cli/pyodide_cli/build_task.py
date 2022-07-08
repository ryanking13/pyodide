import argparse
import os
import shutil
from pathlib import Path

import pyodide_build.buildpkg
from pyodide_build.buildpkg import get_bash_runner
from pyodide_build.common import search_pyodide_root

# from doit.reporter import ZeroReporter

DOIT_CONFIG = {
    "verbosity": 2,
    "minversion": "0.36.0",
    "action_string_formatting": "both",
    # "reporter": ZeroReporter,
}

PYODIDE_ROOT = search_pyodide_root(os.getcwd())
JS_DIR = PYODIDE_ROOT / "src/js"
PYTHON_DIR = PYODIDE_ROOT / "src/py"
CORE_DIR = PYODIDE_ROOT / "src/core"
DIST_DIR = PYODIDE_ROOT / "dist"
TEMPLATES_DIR = PYODIDE_ROOT / "src/templates"


def bash_runner(cmds):
    if isinstance(cmds, str):
        cmds = [cmds]

    with get_bash_runner() as runner:
        for cmd in cmds:
            runner.run(cmd)


def task_package():
    def build_package(name):
        parser = pyodide_build.buildpkg.make_parser(argparse.ArgumentParser())
        args = parser.parse_args([name])
        pyodide_build.buildpkg.main(args)

    return {
        "actions": [(build_package,)],
        "params": [
            {
                "name": "name",
                "long": "name",
                "type": str,
                "default": "",
            }
        ],
        "clean": True,
    }


def task_cpython():
    cpythonlib = Path(os.environ["CPYTHONLIB"])
    return {
        "file_dep": [PYODIDE_ROOT / "cpython/Makefile"],
        "actions": [
            f". {PYODIDE_ROOT / 'emsdk/emsdk/emsdk_env.sh'} && make -C cpython",
        ],
        "targets": [
            cpythonlib.parent / "libpython3.10.a",
        ],
        "task_dep": ["emsdk"],
        "clean": True,
    }


def task_emsdk():
    return {
        "file_dep": [PYODIDE_ROOT / "emsdk/Makefile"],
        "actions": ["make -C emsdk"],
        "targets": [PYODIDE_ROOT / "emsdk/emsdk/.complete"],
        "clean": True,
    }


def task_pyodide_core():
    compilers = {
        ".c": "emcc",
        ".cpp": "em++",
    }
    for ext, compiler in compilers.items():
        for source in CORE_DIR.glob(f"*{ext}"):
            target = source.with_suffix(".o")
            yield {
                "name": source.name,
                "file_dep": [source],
                "actions": [
                    (
                        bash_runner,
                        [
                            f"{compiler} -c {source} -o {target} $MAIN_MODULE_CFLAGS -I{str(CORE_DIR)}"
                        ],
                    ),
                ],
                "targets": [target],
                "task_dep": ["cpython"],
                "clean": True,
            }


def task_install_js_deps():
    return {
        "file_dep": [JS_DIR / "package.json", JS_DIR / "package-lock.json"],
        "actions": [
            f"cd {JS_DIR} && npm ci",
            f"ln -sfn {JS_DIR}/node_modules {PYODIDE_ROOT}/node_modules",
            f"touch {PYODIDE_ROOT}/node_modules/.installed",
        ],
        "targets": [PYODIDE_ROOT / "node_modules/.installed"],
        "clean": True,
    }


def task_pyproxy_gen():
    # We can't input pyproxy.js directly because CC will be unhappy about the file
    # extension. Instead cat it and have CC read from stdin.
    # -E : Only apply prepreocessor
    # -C : Leave comments alone (this allows them to be preserved in typescript
    #      definition files, rollup will strip them out)
    # -P : Don't put in macro debug info
    # -imacros pyproxy.c : include all of the macros definitions from pyproxy.c
    #
    # First we use sed to delete the segments of the file between
    # "// pyodide-skip" and "// end-pyodide-skip". This allows us to give typescript type
    # declarations for the macros which we need for intellisense
    # and documentation generation. The result of processing the type
    # declarations with the macro processor is a type error, so we snip them
    # out.

    return {
        "file_dep": [*CORE_DIR.glob("pyproxy.*"), *CORE_DIR.glob("*.h")],
        "actions": [
            (
                bash_runner,
                [
                    f"""
                    rm -f {JS_DIR}/pyproxy.gen.ts
                    echo "// This file is generated by applying the C preprocessor to core/pyproxy.ts" >> {JS_DIR}/pyproxy.gen.ts
                    echo "// It uses the macros defined in core/pyproxy.c" >> {JS_DIR}/pyproxy.gen.ts
                    echo "// Do not edit it directly!" >> {JS_DIR}/pyproxy.gen.ts
                    cat {CORE_DIR}/pyproxy.ts | \
                        sed '/^\\/\\/\\s*pyodide-skip/,/^\\/\\/\\s*end-pyodide-skip/d' | \
                        emcc -E -C -P -imacros {CORE_DIR}/pyproxy.c $MAIN_MODULE_CFLAGS - \
                        >> {JS_DIR}/pyproxy.gen.ts
                    """
                ],
            )
        ],
        "targets": [JS_DIR / "pyproxy.gen.ts"],
        "clean": True,
    }


def task_error_handling():
    return {
        "file_dep": [CORE_DIR / "error_handling.ts"],
        "actions": [
            f"cp {CORE_DIR / 'error_handling.ts'} {JS_DIR / 'error_handling.gen.ts'}"
        ],
        "targets": [JS_DIR / "error_handling.gen.ts"],
        "clean": True,
    }


def task_pyodide_js():
    build_config = JS_DIR / "rollup.config.js"
    return {
        "file_dep": [
            *JS_DIR.glob("*.ts"),
        ],
        "actions": [
            (bash_runner, [f"npx rollup -c {build_config}"]),
        ],
        "targets": [DIST_DIR / "pyodide.js", JS_DIR / "_pyodide.out.js"],
        "task_dep": [
            "install_js_deps",
            "error_handling",
            "pyproxy_gen",
            "distutils",
        ],
        "clean": True,
    }


def task_pyodide_asm_js():
    target = DIST_DIR / "pyodide.asm.js"
    objs = [str(p) for p in CORE_DIR.glob("*.o")]
    return {
        "file_dep": [*objs],
        "actions": [
            (
                # TODO: replace makefile internal filterfunc with a proper
                bash_runner,
                [
                    (
                        'date +"[%F %T] Building pyodide.asm.js..."',
                        f"""
                        [ -d {DIST_DIR} ] || mkdir {DIST_DIR}
                        emcc -o {target} {" ".join(objs)} $MAIN_MODULE_LDFLAGS
                        """,
                        # Strip out C++ symbols which all start __Z.
                        # There are 4821 of these and they have VERY VERY long names.
                        # To show some stats on the symbols you can use the following:
                        # cat {target} | grep -ohE 'var _{{0,5}}.' | sort | uniq -c | sort -nr | head -n 20
                        f"""
                        sed -i -E 's/var __Z[^;]*;//g' {target}
                        sed -i '1i "use strict";' {target}
                        """,
                        # Remove last 6 lines of pyodide.asm.js, see issue #2282
                        # Hopefully we will remove this after emscripten fixes it, upstream issue
                        # emscripten-core/emscripten#16518
                        # Sed nonsense from https://stackoverflow.com/a/13383331
                        f"""
                        sed -i -n -e :a -e '1,6!{{P;N;D;}};N;ba' {target}
                        echo "globalThis._createPyodideModule = _createPyodideModule;" >> {target}
                        """,
                        'date +"[%F %T] done building pyodide.asm.js."',
                    )
                ],
            )
        ],
        "targets": [target],
        "task_dep": ["pyodide_core", "pyodide_js"],
        "clean": True,
    }


def task_pyodide_d_ts():
    return {
        "file_dep": [JS_DIR / "pyodide.ts"],
        "actions": [
            "npx dts-bundle-generator {dependencies} --export-referenced-types false",
            f"mv {JS_DIR / 'pyodide.d.ts'} dist",
        ],
        "targets": [DIST_DIR / "pyodide.d.ts"],
        "task_dep": ["pyodide_js", "error_handling", "pyproxy_gen"],
        "clean": True,
    }


def task_templates():
    targets = {
        "webworker.js": TEMPLATES_DIR / "webworker.js",
        "webworker_dev.js": TEMPLATES_DIR / "webworker.js",
        "module_webworker_dev.js": TEMPLATES_DIR / "module_webworker.js",
        "test.html": TEMPLATES_DIR / "test.html",
        "module_test.html": TEMPLATES_DIR / "module_test.html",
    }

    for target, source in targets.items():
        yield {
            "name": target,
            "file_dep": [source],
            "actions": [
                (
                    bash_runner,
                    [f"cp {source} {DIST_DIR / target}"],
                ),
            ],
            "targets": [DIST_DIR / target],
            "clean": True,
        }


def task_pyodide_py():
    pyodide = PYTHON_DIR / "pyodide"
    pyodide_internal = PYTHON_DIR / "_pyodide"
    return {
        "file_dep": [*pyodide.glob("*.py"), *pyodide_internal.glob("*.py")],
        "actions": [
            f"tar --exclude '*__pycache__*' -cf {DIST_DIR / 'pyodide_py.tar'} -C {PYTHON_DIR} {pyodide.name} {pyodide_internal.name}"
        ],
        "targets": [DIST_DIR / "pyodide_py.tar"],
        "clean": True,
    }


def task_repodata_json():
    return {
        "actions": [
            'date +"[%%F %%T] Building packages..."',
            "make -C packages",
            'date +"[%%F %%T] done building packages..."',
        ],
        "targets": [DIST_DIR / "repodata.json"],
        "clean": True,
    }


def task_distutils():
    cpythonlib = Path(os.environ["CPYTHONLIB"])
    return {
        "task_dep": ["cpython"],
        "file_dep": [*(cpythonlib / "distutils").glob("**/*.py")],
        "actions": [
            f"tar --exclude=__pycache__ -cf {DIST_DIR / 'distutils.tar'} -C {cpythonlib} distutils"
        ],
        "targets": [DIST_DIR / "distutils.tar"],
        "clean": True,
    }


def task_package_json():
    package_json = JS_DIR / "package.json"
    return {
        "file_dep": [package_json],
        "actions": [f"mkdir -p {DIST_DIR}", f"cp {package_json} {DIST_DIR}"],
        "targets": [DIST_DIR / "package.json"],
        "clean": True,
    }


def task_console_html():
    console_html = TEMPLATES_DIR / "console.html"
    base_url = os.environ["PYODIDE_BASE_URL"]
    return {
        "file_dep": [console_html],
        "actions": [
            f"cp {console_html} {DIST_DIR / 'console.html'}",
            "sed -i -e 's#{{{{{{{{ PYODIDE_BASE_URL }}}}}}}}#{}#g' {}".format(
                base_url, str(DIST_DIR / "console.html")
            ),
        ],
        "targets": [DIST_DIR / "console.html"],
        "clean": True,
    }


def task_dependency_check():
    return {"actions": ["echo FIXME!"]}


def task_test():
    test_extensions = [
        (
            "_testinternalcapi.c",
            "_testinternalcapi.o",
            "-I Include/internal/ -DPy_BUILD_CORE_MODULE",
        ),
        ("_testcapimodule.c", "_testcapi.o", ""),
        ("_testbuffer.c", "_testbuffer.o", ""),
        ("_testimportmultiple.c", "_testimportmultiple.o", ""),
        ("_testmultiphase.c", "_testmultiphase.o", ""),
        ("_ctypes/_ctypes_test.c", "_ctypes_test.o", ""),
    ]
    test_module_cflags = os.environ["SIDE_MODULE_CFLAGS"] + " -I Include/ -I ."
    cpythonbuild = Path(os.environ["CPYTHONBUILD"])
    cpythonlib = Path(os.environ["CPYTHONLIB"])
    for source, obj, flags in test_extensions:
        lib = Path(obj).with_suffix(".so")
        yield {
            "name": source,
            "task_dep": ["cpython"],
            "actions": [
                f"cd {cpythonbuild} && emcc {test_module_cflags} -c Modules/{source} -o Modules/{obj} {flags}",
                f"cd {cpythonbuild} && emcc Modules/{obj} -o {lib} $SIDE_MODULE_LDFLAGS",
                f"cd {cpythonbuild} && rm -f {cpythonlib / lib} && ln -s {cpythonbuild / lib} {cpythonlib / lib}",
            ],
            "targets": [cpythonbuild / lib, cpythonlib / lib],
            "clean": True,
        }


def task_dist_test():
    test_extensions = [
        "_testinternalcapi.so",
        "_testcapi.so",
        "_testbuffer.so",
        "_testimportmultiple.so",
        "_testmultiphase.so",
        "_ctypes_test.so",
    ]
    test_extensions_str = " ".join(test_extensions)
    return {
        "task_dep": ["test"],
        "actions": [
            (
                f"cd $CPYTHONLIB && tar -h --exclude=__pycache__ -cf {DIST_DIR / 'test.tar'} "
                f"test {test_extensions_str} unittest/test sqlite3/test ctypes/test"
            ),
            f"cd $CPYTHONLIB && rm {test_extensions_str}",
        ],
        "targets": [DIST_DIR / "test.tar"],
        "clean": True,
    }


def task_pyodide():
    return {
        "task_dep": [
            "dependency_check",
            "pyodide_asm_js",
            "pyodide_js",
            "pyodide_d_ts",
            "package_json",
            "console_html",
            "distutils",
            "dist_test",
            "repodata_json",
            "pyodide_py",
            "templates",
        ],
        "actions": ['echo "SUCCESS!"'],
        "clean": [lambda: shutil.rmtree(DIST_DIR, ignore_errors=True)],
    }
