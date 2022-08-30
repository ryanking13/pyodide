# Pyodide uses "wrapper approach":
# we hijack calls to gcc, g++, ... and redirect them to emcc with some modifications.
# so sometimes we need to tell cmake to call host compiler instead of emcc.

set(CMAKE_C_COMPILER "")
set(CMAKE_CXX_COMPILER "")
set(CMAKE_AR "")
set(CMAKE_RANLIB "")
set(CMAKE_C_COMPILER_AR "")
set(CMAKE_CXX_COMPILER_AR "")
set(CMAKE_C_COMPILER_RANLIB "")
set(CMAKE_CXX_COMPILER_RANLIB "")
