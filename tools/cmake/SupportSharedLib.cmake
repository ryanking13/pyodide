# Note: this is False in original Emscripten toolchain,
#       however we always want to allow build shared libs
#       (See also: https://github.com/emscripten-core/emscripten/pull/16281)

# FIXME: For some reason, setting this value inside the toolchain file is ignored...
set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)
