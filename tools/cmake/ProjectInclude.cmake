# FIXME: For some reason, setting this value inside the toolchain file is ignored...

# Note: this is False in original Emscripten toolchain,
#       however we always want to allow build shared libs
#       (See also: https://github.com/emscripten-core/emscripten/pull/16281)

set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)

# Note: Disable the usage of response file so objects are exposed to the commandline.
#       Our export calculation logic in pywasmcross needs to read object files.
set(CMAKE_C_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_OBJECTS 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_OBJECTS 0)
