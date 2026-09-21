#include "emscripten.h"
#include "jslib.h"
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <wasi/api.h>

extern int
syscall_syncify(JsVal promise);

// Keep the default syscall path entirely in Wasm until automatic NativeFS
// synchronization is first enabled. This flag intentionally stays enabled
// because mounts can be removed through the public FS API without notifying C.
bool nativefs_autosync_enabled = false;

// Return the automatic NativeFS mount associated with fd. If writable_only is
// true, read-only streams are ignored so closing them does not trigger a sync.
// clang-format off
EM_JS(JsVal, nativefs_context_for_fd, (int fd, bool writable_only), {
  const stream = Module.FS.getStream(fd);
  if (!stream || (writable_only && !(stream.flags & 3))) {
    return null;
  }
  const mount = stream.node.mount;
  if (mount?.type !== Module.FS.filesystems.NATIVEFS_ASYNC ||
      !mount.opts.autoSync) {
    return null;
  }
  if (!validSuspender.value) {
    return false;
  }
  return { mount, paths: [Module.FS.getPath(stream.node)] };
})

// Resolve an Emscripten *at path before a destructive syscall invalidates it.
// Lookup failures are left to the real syscall so it can preserve errno.
EM_JS(JsVal,
       nativefs_context_for_path,
      (int dirfd, intptr_t path_ptr, bool parent),
      {
        let path;
        let mount;
        try {
          path = SYSCALLS.calculateAt(dirfd, UTF8ToString(path_ptr));
          mount = Module.FS.lookupPath(path, { parent }).node.mount;
        } catch (e) {
          return null;
        }
        if (mount?.type !== Module.FS.filesystems.NATIVEFS_ASYNC ||
            !mount.opts.autoSync) {
          return null;
        }
        if (!validSuspender.value) {
          return false;
        }
        return { mount, paths: [path] };
       })

EM_JS(void, nativefs_context_merge, (JsVal context, JsVal other), {
  if (context && other && context.mount === other.mount) {
    context.paths.push(...other.paths);
  }
})

EM_JS(JsVal, nativefs_sync_context, (JsVal context), {
  const mount = context.mount;
  if (!mount.opts.autoSyncPaths) {
    mount.opts.autoSyncPaths = new Set();
  }
  for (const path of context.paths) {
    mount.opts.autoSyncPaths.add(path);
  }
  return new Promise((resolve) => {
    mount.type.syncfs(mount, false, (error) => {
      resolve(error ? Module.ERRNO_CODES.EIO : 0);
    });
  });
})

EM_JS(bool, nativefs_context_has_error, (JsVal context), {
  return context === false;
})
// clang-format on

static bool
has_context(JsVal context)
{
  return !__builtin_wasm_ref_is_null_extern(context);
}

static int
sync_context(JsVal context)
{
  if (!has_context(context)) {
    return 0;
  }
  int result = syscall_syncify(nativefs_sync_context(context));
  return result == 0 ? 0 : EIO;
}

__wasi_errno_t
__real___wasi_fd_close(__wasi_fd_t fd);

__wasi_errno_t
__wrap___wasi_fd_close(__wasi_fd_t fd)
{
  if (!nativefs_autosync_enabled) {
    return __real___wasi_fd_close(fd);
  }
  JsVal context = nativefs_context_for_fd(fd, true);
  if (nativefs_context_has_error(context)) {
    return __WASI_ERRNO_IO;
  }
  __wasi_errno_t result = __real___wasi_fd_close(fd);
  if (result != __WASI_ERRNO_SUCCESS) {
    return result;
  }
  return sync_context(context) == 0 ? __WASI_ERRNO_SUCCESS : __WASI_ERRNO_IO;
}

__wasi_errno_t
__real___wasi_fd_sync(__wasi_fd_t fd);

__wasi_errno_t
__wrap___wasi_fd_sync(__wasi_fd_t fd)
{
  if (!nativefs_autosync_enabled) {
    return __real___wasi_fd_sync(fd);
  }
  JsVal context = nativefs_context_for_fd(fd, false);
  if (nativefs_context_has_error(context)) {
    return __WASI_ERRNO_IO;
  }
  __wasi_errno_t result = __real___wasi_fd_sync(fd);
  if (result != __WASI_ERRNO_SUCCESS) {
    return result;
  }
  return sync_context(context) == 0 ? __WASI_ERRNO_SUCCESS : __WASI_ERRNO_IO;
}

int
__real___syscall_fdatasync(int fd);

int
__wrap___syscall_fdatasync(int fd)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_fdatasync(fd);
  }
  JsVal context = nativefs_context_for_fd(fd, false);
  if (nativefs_context_has_error(context)) {
    return -EIO;
  }
  int result = __real___syscall_fdatasync(fd);
  if (result != 0) {
    return result;
  }
  return sync_context(context) == 0 ? 0 : -EIO;
}

int
__real___syscall_truncate64(intptr_t path, int64_t length);

int
__wrap___syscall_truncate64(intptr_t path, int64_t length)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_truncate64(path, length);
  }
  JsVal context = nativefs_context_for_path(AT_FDCWD, path, false);
  if (nativefs_context_has_error(context)) {
    return -EIO;
  }
  int result = __real___syscall_truncate64(path, length);
  if (result != 0) {
    return result;
  }
  return sync_context(context) == 0 ? 0 : -EIO;
}

int
__real___syscall_ftruncate64(int fd, int64_t length);

int
__wrap___syscall_ftruncate64(int fd, int64_t length)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_ftruncate64(fd, length);
  }
  JsVal context = nativefs_context_for_fd(fd, false);
  if (nativefs_context_has_error(context)) {
    return -EIO;
  }
  int result = __real___syscall_ftruncate64(fd, length);
  if (result != 0) {
    return result;
  }
  return sync_context(context) == 0 ? 0 : -EIO;
}

int
__real___syscall_mkdirat(int dirfd, intptr_t path, int mode);

int
__wrap___syscall_mkdirat(int dirfd, intptr_t path, int mode)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_mkdirat(dirfd, path, mode);
  }
  JsVal context = nativefs_context_for_path(dirfd, path, true);
  if (nativefs_context_has_error(context)) {
    return -EIO;
  }
  int result = __real___syscall_mkdirat(dirfd, path, mode);
  if (result != 0) {
    return result;
  }
  return sync_context(context) == 0 ? 0 : -EIO;
}

int
__real___syscall_rmdir(intptr_t path);

int
__wrap___syscall_rmdir(intptr_t path)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_rmdir(path);
  }
  JsVal context = nativefs_context_for_path(AT_FDCWD, path, false);
  if (nativefs_context_has_error(context)) {
    return -EIO;
  }
  int result = __real___syscall_rmdir(path);
  if (result != 0) {
    return result;
  }
  return sync_context(context) == 0 ? 0 : -EIO;
}

int
__real___syscall_unlinkat(int dirfd, intptr_t path, int flags);

int
__wrap___syscall_unlinkat(int dirfd, intptr_t path, int flags)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_unlinkat(dirfd, path, flags);
  }
  JsVal context = nativefs_context_for_path(dirfd, path, false);
  if (nativefs_context_has_error(context)) {
    return -EIO;
  }
  int result = __real___syscall_unlinkat(dirfd, path, flags);
  if (result != 0) {
    return result;
  }
  return sync_context(context) == 0 ? 0 : -EIO;
}

int
__real___syscall_renameat(int olddirfd,
                          intptr_t oldpath,
                          int newdirfd,
                          intptr_t newpath);

int
__wrap___syscall_renameat(int olddirfd,
                          intptr_t oldpath,
                          int newdirfd,
                          intptr_t newpath)
{
  if (!nativefs_autosync_enabled) {
    return __real___syscall_renameat(olddirfd, oldpath, newdirfd, newpath);
  }
  JsVal context = nativefs_context_for_path(olddirfd, oldpath, false);
  JsVal new_context = nativefs_context_for_path(newdirfd, newpath, true);
  if (nativefs_context_has_error(context) ||
      nativefs_context_has_error(new_context)) {
    return -EIO;
  }
  int result = __real___syscall_renameat(olddirfd, oldpath, newdirfd, newpath);
  if (result != 0) {
    return result;
  }
  nativefs_context_merge(context, new_context);
  return sync_context(context) == 0 ? 0 : -EIO;
}
