"""tests of using the emscripten filesystem API with pyodide

for a basic nodejs-based test, see src/js/test/filesystem.test.js
"""

import pytest
from pytest_pyodide import run_in_pyodide

from conftest import only_chrome, only_node, requires_jspi


@pytest.mark.skip_refcount_check
@pytest.mark.skip_pyproxy_check
def test_idbfs_persist_code(selenium_standalone_refresh):
    """can we persist files created by user python code?"""
    selenium = selenium_standalone_refresh
    if selenium.browser == "node":
        fstype = "NODEFS"
    else:
        fstype = "IDBFS"

    mount_dir = "/mount_test"
    # create mount
    selenium.run_js(
        f"""
        let mountDir = '{mount_dir}';
        pyodide.FS.mkdir(mountDir);
        pyodide.FS.mount(pyodide.FS.filesystems.{fstype}, {{root : "."}}, mountDir);
        """
    )

    @run_in_pyodide
    def create_test_file(selenium_module, mount_dir):
        import sys
        from importlib import invalidate_caches
        from pathlib import Path

        p = Path(f"{mount_dir}/test_idbfs/__init__.py")
        p.parent.mkdir(exist_ok=True, parents=True)
        p.write_text("def test(): return 7")
        invalidate_caches()
        sys.path.append(mount_dir)
        from test_idbfs import test

        assert test() == 7

    create_test_file(selenium, mount_dir)
    # sync TO idbfs
    selenium.run_js(
        """
        const error = await new Promise(
            (resolve, reject) => pyodide.FS.syncfs(false, resolve)
        );
        assert(() => error == null);
        """
    )
    # refresh page and re-fixture
    selenium.refresh()
    selenium.run_js(
        """
        self.pyodide = await loadPyodide();
        """
    )
    # idbfs isn't magically loaded
    selenium.run_js(
        f"""
        pyodide.runPython(`
            from importlib import invalidate_caches
            import sys
            invalidate_caches()
            err_type = None
            try:
                sys.path.append('{mount_dir}')
                from test_idbfs import test
            except Exception as err:
                err_type = type(err)
            assert err_type is ModuleNotFoundError, err_type
        `);
        """
    )
    # re-mount
    selenium.run_js(
        f"""
        pyodide.FS.mkdir('{mount_dir}');
        pyodide.FS.mount(pyodide.FS.filesystems.{fstype}, {{root : "."}}, "{mount_dir}");
        """
    )
    # sync FROM idbfs
    selenium.run_js(
        """
        const error = await new Promise(
            (resolve, reject) => pyodide.FS.syncfs(true, resolve)
        );
        assert(() => error == null);
        """
    )
    # import file persisted above
    selenium.run_js(
        f"""
        pyodide.runPython(`
            from importlib import invalidate_caches
            invalidate_caches()
            import sys
            sys.path.append('{mount_dir}')
            from test_idbfs import test
            assert test() == 7
        `);
        """
    )
    # remove file
    selenium.run_js(f"""pyodide.FS.unlink("{mount_dir}/test_idbfs/__init__.py")""")


@pytest.mark.requires_dynamic_linking
@only_chrome
def test_nativefs_dir(request, selenium_standalone_refresh):
    # Note: Using *real* native file system requires
    # user interaction so it is not available in headless mode.
    # So in this test we use OPFS (Origin Private File System)
    # which is part of File System Access API but uses indexDB as a backend.

    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_standalone_refresh

    selenium.run_js(
        """
        root = await navigator.storage.getDirectory();
        dirHandleMount = await root.getDirectoryHandle('testdir', { create: true });
        testFileHandle = await dirHandleMount.getFileHandle('test_read', { create: true });
        writable = await testFileHandle.createWritable();
        await writable.write("hello_read");
        await writable.close();
        fs = await pyodide.mountNativeFS("/mnt/nativefs", dirHandleMount);
        assert(() => pyodide._module.HEAP8[
          pyodide._module._nativefs_autosync_enabled
        ] === 0);
        """
    )

    # Read

    selenium.run(
        """
        import os
        import pathlib
        assert len(os.listdir("/mnt/nativefs")) == 1, str(os.listdir("/mnt/nativefs"))
        assert os.listdir("/mnt/nativefs") == ["test_read"], str(os.listdir("/mnt/nativefs"))

        pathlib.Path("/mnt/nativefs/test_read").read_text() == "hello_read"
        """
    )

    # Write / Delete / Rename

    selenium.run(
        """
        import os
        import pathlib
        pathlib.Path("/mnt/nativefs/test_write").write_text("hello_write")
        pathlib.Path("/mnt/nativefs/test_write").read_text() == "hello_write"
        pathlib.Path("/mnt/nativefs/test_delete").write_text("This file will be deleted")
        pathlib.Path("/mnt/nativefs/test_rename").write_text("This file will be renamed")
        """
    )

    entries = selenium.run_js(
        """
        await fs.syncfs();
        entries = {};
        for await (const [key, value] of dirHandleMount.entries()) {
            entries[key] = value;
        }
        return entries;
        """
    )

    assert "test_read" in entries
    assert "test_write" in entries
    assert "test_delete" in entries
    assert "test_rename" in entries

    selenium.run(
        """
        import os
        os.remove("/mnt/nativefs/test_delete")
        os.rename("/mnt/nativefs/test_rename", "/mnt/nativefs/test_rename_renamed")
        """
    )

    entries = selenium.run_js(
        """
        await fs.syncfs();
        entries = {};
        for await (const [key, value] of dirHandleMount.entries()) {
            entries[key] = value;
        }
        return entries;
        """
    )

    assert "test_delete" not in entries
    assert "test_rename" not in entries
    assert "test_rename_renamed" in entries

    # unmount

    files = selenium.run(
        """
        import os
        os.listdir("/mnt/nativefs")
        """
    )

    assert "test_read" in entries
    assert "test_write" in entries
    assert "test_rename_renamed" in entries

    selenium.run_js(
        """
        await fs.syncfs();
        pyodide.FS.unmount("/mnt/nativefs");
        """
    )

    files = selenium.run(
        """
        import os
        os.listdir("/mnt/nativefs")
        """
    )

    assert not len(files)

    # Mount again

    selenium.run_js(
        """
        fs2 = await pyodide.mountNativeFS("/mnt/nativefs", dirHandleMount);
        """
    )

    # Read again

    selenium.run(
        """
        import os
        import pathlib
        assert len(os.listdir("/mnt/nativefs")) == 3, str(os.listdir("/mnt/nativefs"))
        pathlib.Path("/mnt/nativefs/test_read").read_text() == "hello_read"
        """
    )

    selenium.run_js(
        """
        await fs2.syncfs();
        pyodide.FS.unmount("/mnt/nativefs");
        """
    )


@only_chrome
def test_nativefs_errors(selenium):
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const handle = await root.getDirectoryHandle("dir", { create: true });

        await pyodide.mountNativeFS("/mnt1/nativefs", handle);
        await assertThrowsAsync(
          async () => await pyodide.mountNativeFS("/mnt1/nativefs", handle),
          "Error",
          "path '/mnt1/nativefs' is already a file system mount point",
        );

        pyodide.FS.mkdirTree("/mnt2");
        pyodide.FS.writeFile("/mnt2/some_file", "contents");
        await assertThrowsAsync(
          async () => await pyodide.mountNativeFS("/mnt2/some_file", handle),
          "Error",
          "path '/mnt2/some_file' points to a file not a directory",
        );
        // Check we didn't overwrite the file.
        assert(
          () =>
            pyodide.FS.readFile("/mnt2/some_file", { encoding: "utf8" }) === "contents",
        );

        pyodide.FS.mkdirTree("/mnt3/nativefs");
        pyodide.FS.writeFile("/mnt3/nativefs/a.txt", "contents");
        await assertThrowsAsync(
          async () => await pyodide.mountNativeFS("/mnt3/nativefs", handle),
          "Error",
          "directory '/mnt3/nativefs' is not empty",
        );
        // Check directory wasn't changed
        const { node } = pyodide.FS.lookupPath("/mnt3/nativefs/");
        assert(() => Object.entries(node.contents).length === 1);
        assert(
          () =>
            pyodide.FS.readFile("/mnt3/nativefs/a.txt", { encoding: "utf8" }) ===
            "contents",
        );

        const [r1, r2] = await Promise.allSettled([
          pyodide.mountNativeFS("/mnt4/nativefs", handle),
          pyodide.mountNativeFS("/mnt4/nativefs", handle),
        ]);
        assert(() => r1.status === "fulfilled");
        assert(() => r2.status === "rejected");
        assert(
          () =>
            r2.reason.message === "path '/mnt4/nativefs' is already a file system mount point",
        );
        """
    )


@pytest.mark.requires_dynamic_linking
@only_chrome
@requires_jspi
def test_nativefs_jspi_sync(request, selenium_standalone_refresh):
    if request.config.option.runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    selenium = selenium_standalone_refresh
    selenium.run_js(
        """
        root = await navigator.storage.getDirectory();
        await root.removeEntry("nativefs-jspi", { recursive: true }).catch(() => {});
        dirHandleMount = await root.getDirectoryHandle(
          "nativefs-jspi",
          { create: true },
        );
        assert(() => pyodide._module.HEAP8[
          pyodide._module._nativefs_autosync_enabled
        ] === 0);
        await pyodide.mountNativeFS("/mnt/nativefs-jspi", dirHandleMount, true);
        assert(() => pyodide._module.HEAP8[
          pyodide._module._nativefs_autosync_enabled
        ] === 1);

        assertThrows(
          () => pyodide.runPython(`
            from pathlib import Path
            Path("/mnt/nativefs-jspi/not-created").mkdir()
          `),
          "PythonError",
          "I/O error",
        );
        """
    )

    def read_remote_file(name):
        return selenium.run_js(
            f"""
            const handle = await dirHandleMount.getFileHandle({name!r});
            return await (await handle.getFile()).text();
            """
        )

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          from pathlib import Path
          Path("/mnt/nativefs-jspi/file.txt").write_text("contents")
        `);
        """
    )
    assert read_remote_file("file.txt") == "contents"

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          from pathlib import Path
          Path("/mnt/nativefs-jspi/directory").mkdir()
          Path("/mnt/nativefs-jspi/old.txt").write_text("renamed")
        `);
        await dirHandleMount.getDirectoryHandle("directory");
        await pyodide.runPythonAsync(`
          import os
          os.rename(
            "/mnt/nativefs-jspi/old.txt",
            "/mnt/nativefs-jspi/new.txt",
          )
        `);
        """
    )
    assert read_remote_file("new.txt") == "renamed"
    old_exists = selenium.run_js(
        """
        return await dirHandleMount.getFileHandle("old.txt")
          .then(() => true, () => false);
        """
    )
    assert not old_exists

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          import os
          from pathlib import Path
          source = Path("/mnt/nativefs-jspi/overwrite-source.txt")
          source.write_text("replacement")
          Path("/mnt/nativefs-jspi/overwrite-destination.txt").write_text("stale")
          os.utime(source, ns=(1_000_000, 1_000_000))
          os.rename(
            source,
            "/mnt/nativefs-jspi/overwrite-destination.txt",
          )
        `);
        """
    )
    assert read_remote_file("overwrite-destination.txt") == "replacement"

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          from pathlib import Path
          Path("/mnt/nativefs-jspi/failed-rename.txt").write_text("local")
        `);
        await new Promise((resolve) => setTimeout(resolve, 10));
        const failedRenameHandle = await dirHandleMount.getFileHandle(
          "failed-rename.txt",
        );
        const failedRenameWritable = await failedRenameHandle.createWritable();
        await failedRenameWritable.write("remote-newer");
        await failedRenameWritable.close();
        await pyodide.runPythonAsync(`
          import os
          from pathlib import Path
          try:
            os.rename(
              "/mnt/nativefs-jspi/failed-rename.txt",
              "/mnt/nativefs-jspi/missing/failed-rename.txt",
            )
          except OSError:
            pass
          Path("/mnt/nativefs-jspi/failed-rename-trigger").mkdir()
        `);
        """
    )
    assert read_remote_file("failed-rename.txt") == "remote-newer"

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          import os
          os.truncate("/mnt/nativefs-jspi/file.txt", 4)
        `);
        """
    )
    assert read_remote_file("file.txt") == "cont"

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          import os
          nativefs_fd = os.open("/mnt/nativefs-jspi/file.txt", os.O_RDWR)
          os.ftruncate(nativefs_fd, 2)
        `);
        """
    )
    assert read_remote_file("file.txt") == "co"
    selenium.run_js('await pyodide.runPythonAsync("os.close(nativefs_fd)");')

    for sync_call in ["fsync", "fdatasync"]:
        selenium.run_js(
            f"""
            await pyodide.runPythonAsync(`
              import os
              nativefs_fd = os.open(
                "/mnt/nativefs-jspi/{sync_call}.txt",
                os.O_CREAT | os.O_WRONLY,
              )
              os.write(nativefs_fd, b"{sync_call}")
              os.{sync_call}(nativefs_fd)
            `);
            """
        )
        assert read_remote_file(f"{sync_call}.txt") == sync_call
        selenium.run_js('await pyodide.runPythonAsync("os.close(nativefs_fd)");')

    selenium.run_js(
        """
        await pyodide.runPythonAsync(`
          import os
          os.unlink("/mnt/nativefs-jspi/new.txt")
          os.rmdir("/mnt/nativefs-jspi/directory")
        `);
        """
    )
    entries = selenium.run_js(
        """
        const result = [];
        for await (const key of dirHandleMount.keys()) result.push(key);
        return result;
        """
    )
    assert "new.txt" not in entries
    assert "directory" not in entries


@only_chrome
def test_nativefs_jspi_requires_jspi(selenium):
    selenium.run_js(
        """
        const root = await navigator.storage.getDirectory();
        const handle = await root.getDirectoryHandle(
          "nativefs-jspi-unsupported",
          { create: true },
        );
        const original = pyodide._module.jspiSupported;
        pyodide._module.jspiSupported = false;
        try {
          await assertThrowsAsync(
            () => pyodide.mountNativeFS("/mnt/nativefs-jspi-unsupported", handle, true),
            "Error",
            "Synchronous native file system mounts require JSPI support",
          );
        } finally {
          pyodide._module.jspiSupported = original;
        }
        assert(() => !pyodide.FS.analyzePath("/mnt/nativefs-jspi-unsupported").exists);
        """
    )


@only_node
def test_mount_nodefs(selenium):
    selenium.run_js(
        """
        pyodide.mountNodeFS("/mnt1/nodefs", ".");
        assertThrows(
          () => pyodide.mountNodeFS("/mnt1/nodefs", "."),
          "Error",
          "path '/mnt1/nodefs' is already a file system mount point"
        );

        assertThrows(
          () =>
            pyodide.mountNodeFS(
              "/mnt2/nodefs",
              "/thispath/does-not/exist/ihope"
            ),
          "Error",
          "hostPath '/thispath/does-not/exist/ihope' does not exist"
        );

        const os = require("os");
        const fs = require("fs");
        const path = require("path");
        const crypto = require("crypto");
        const tmpdir = path.join(os.tmpdir(), crypto.randomUUID());
        fs.mkdirSync(tmpdir);
        const apath = path.join(tmpdir, "a");
        fs.writeFileSync(apath, "xyz");
        pyodide.mountNodeFS("/mnt3/nodefs", tmpdir);
        assert(
          () =>
            pyodide.FS.readFile("/mnt3/nodefs/a", { encoding: "utf8" }) ===
            "xyz"
        );

        assertThrows(
          () => pyodide.mountNodeFS("/mnt4/nodefs", apath),
          "Error",
          `hostPath '${apath}' is not a directory`
        );
        """
    )


@pytest.fixture
def browser(selenium):
    return selenium.browser


@pytest.fixture
def runner(request):
    return request.config.option.runner


@run_in_pyodide
def test_fs_dup(selenium, browser):
    from os import close, dup
    from pathlib import Path

    from pyodide.code import run_js

    if browser == "node":
        fstype = "NODEFS"
    else:
        fstype = "IDBFS"

    mount_dir = Path("/mount_test")
    mount_dir.mkdir(exist_ok=True)
    run_js(
        """
        (fstype, mountDir) =>
            pyodide.FS.mount(pyodide.FS.filesystems[fstype], {root : "."}, mountDir);
        """
    )(fstype, str(mount_dir))

    file = open("/mount_test/a.txt", "w")
    fd2 = dup(file.fileno())
    close(fd2)
    file.write("abcd")
    file.close()


@pytest.mark.requires_dynamic_linking
@only_chrome
@run_in_pyodide
async def test_nativefs_dup(selenium, runner):
    from os import close, dup

    import pytest

    from pyodide.code import run_js

    # Note: Using *real* native file system requires
    # user interaction so it is not available in headless mode.
    # So in this test we use OPFS (Origin Private File System)
    # which is part of File System Access API but uses indexDB as a backend.

    if runner == "playwright":
        pytest.xfail("Playwright doesn't support file system access APIs")

    await run_js(
        """
        async () => {
            root = await navigator.storage.getDirectory();
            testFileHandle = await root.getFileHandle('test_read', { create: true });
            writable = await testFileHandle.createWritable();
            await writable.write("hello_read");
            await writable.close();
            await pyodide.mountNativeFS("/mnt/nativefs", root);
        }
        """
    )()
    file = open("/mnt/nativefs/test_read")
    fd2 = dup(file.fileno())
    close(fd2)
    assert file.read() == "hello_read"
    file.close()


def test_trackingDelegate(selenium_standalone_refresh):
    selenium = selenium_standalone_refresh

    selenium.run_js(
        """
        assert (() => typeof pyodide.FS.trackingDelegate !== "undefined")

        if (typeof window !== "undefined") {
            global = window
        } else {
            global = globalThis
        }

        global.trackingLog = ""
        pyodide.FS.trackingDelegate["onCloseFile"] = (path) => { global.trackingLog = `CALLED ${path}` }
        """
    )

    selenium.run(
        """
        f = open("/hello", "w")
        f.write("helloworld")
        f.close()

        import js

        assert "CALLED /hello" in js.trackingLog
        """
    )

    # logs = selenium.logs
    # assert "CALLED /hello" in logs
