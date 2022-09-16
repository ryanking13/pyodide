# This file is a 'toolchain description file' for CMake.
# Based on the toolchain file that Emscripten provides,
# we add some modifications to make it work with Pyodide build system

execute_process(COMMAND "em-config" "EMSCRIPTEN_ROOT"
  RESULT_VARIABLE _emconfig_result
  OUTPUT_VARIABLE _emconfig_output
  OUTPUT_STRIP_TRAILING_WHITESPACE)
if (NOT _emconfig_result EQUAL 0)
  message(FATAL_ERROR "Failed to find emscripten root directory with command \"em-config EMSCRIPTEN_ROOT\"! Process returned with error code ${_emcache_result}.")
endif()

# Note: Disable the usage of response file so objects are exposed to the commandline.
#       Our export calculation logic in pywasmcross needs to read object files.
set(CMAKE_C_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_LIBRARIES 0)
set(CMAKE_C_USE_RESPONSE_FILE_FOR_OBJECTS 0)
set(CMAKE_CXX_USE_RESPONSE_FILE_FOR_OBJECTS 0)

# Note: this is False in original Emscripten toolchain,
#       however we always want to allow build shared libs
#       (See also: https://github.com/emscripten-core/emscripten/pull/16281)
set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)

# We build libraries into WASM_LIBRARY_DIR, so lets tell CMake
# to find libraries from there.
if (NOT "$ENV{WASM_LIBRARY_DIR}" STREQUAL "")
  list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{WASM_LIBRARY_DIR}")
  if (CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT)
    set(CMAKE_INSTALL_PREFIX "$ENV{WASM_LIBRARY_DIR}" CACHE PATH
      "Install path prefix, prepended onto install directories." FORCE)
    # Prevent original Emscripten toolchain from overriding CMAKE_INSTALL_PREFIX again
    set(CMAKE_INSTALL_PREFIX_INITIALIZED_TO_DEFAULT FALSE)
  endif()

endif()

file(TO_CMAKE_PATH "${_emconfig_output}" _emcache_output)
set(EMSCRIPTEN_CMAKE_TOOLCHAIN_FILE "${_emconfig_output}/cmake/Modules/Platform/Emscripten.cmake" CACHE FILEPATH "Path to Emscripten CMake toolchain file.")

# inherit from the Emscripten toolchain file
# loading a toolchain file inside another toolchain file seems
# not a good idea, but we want to inherit all the settings from the Emscripten
include("${EMSCRIPTEN_CMAKE_TOOLCHAIN_FILE}")

# Allow some of the variables to be overridden by the user by env variable
if ("${CMAKE_PROJECT_INCLUDE_BEFORE}" STREQUAL "" AND DEFINED ENV{CMAKE_PROJECT_INCLUDE_BEFORE})
  message(STATUS "Set CMAKE_PROJECT_INCLUDE_BEFORE to $ENV{CMAKE_PROJECT_INCLUDE_BEFORE} using env variable")
  set(CMAKE_PROJECT_INCLUDE_BEFORE "$ENV{CMAKE_PROJECT_INCLUDE_BEFORE}")
endif()

if ("${CMAKE_PROJECT_INCLUDE}" STREQUAL ""  AND DEFINED ENV{CMAKE_PROJECT_INCLUDE})
  message(STATUS "Set CMAKE_PROJECT_INCLUDE to $ENV{CMAKE_PROJECT_INCLUDE} using env variable")
  set(CMAKE_PROJECT_INCLUDE "$ENV{CMAKE_PROJECT_INCLUDE}")
endif()

# Note that if users set there own CMAKE_PROJECT_INCLUDE file, they are responsible for
# setting values in ProjectInclude.cmake.
if ("${CMAKE_PROJECT_INCLUDE}" STREQUAL "")
  message(STATUS "Set CMAKE_PROJECT_INCLUDE to ${CMAKE_CURRENT_LIST_DIR}/../ProjectInclude.cmake")
  set(CMAKE_PROJECT_INCLUDE "${CMAKE_CURRENT_LIST_DIR}/../ProjectInclude.cmake")
endif()

set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} $ENV{SIDE_MODULE_CFLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} $ENV{SIDE_MODULE_CXXFLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} $ENV{SIDE_MODULE_LDFLAGS}")
