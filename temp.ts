type DSO = {
  refcount: number;
  global: boolean;
  name: string;
  module: string | object;
};

/**
 * Load a dynamic library. This function does almost same thing as loadDynamicLibrary()
 * in emscripten, but we add some extra logic to handle complex requirements of Pyodide.
 *
 * @param lib The file system path to the library.
 * @param shared Is this a shared library or not?
 * @private
 */
async function loadDynlibInternal(lib: string, global: boolean) {
  const libName = Module.PATH.basename(lib);

  let dso: DSO = Module.LDSO.loadedLibsByName[libName];
  if (dso) {
    if (global && !dso.global) {
      dso.global = true;
      if (dso.module !== "loading") {
        Module.mergeLibSymbols(dso.module, lib);
      }
    }

    dso.refcount++;
    return Promise.resolve(true);
  }

  // allocate new DSO
  dso = {
    refcount: Infinity,
    name: libName,
    module: "loading",
    global: global,
  };

  Module.LDSO.loadedLibsByName[libName] = dso;

  // 2. create dso module, update LDSO
  // 3. load library data
  // 4. call loadWebAssemblyModule
  // 5. merge symbol if global, and update dso.module
}
