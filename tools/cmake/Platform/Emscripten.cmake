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

# Note that if user sets CMAKE_PROJECT_INCLUDE, they are responsible for
# setting TARGET_SUPPORTS_SHARED_LIBS.
if ("${CMAKE_PROJECT_INCLUDE}" STREQUAL "")
  message(STATUS "Set CMAKE_PROJECT_INCLUDE to ${CMAKE_CURRENT_LIST_DIR}/../SupportSharedLib.cmake")
  set(CMAKE_PROJECT_INCLUDE "${CMAKE_CURRENT_LIST_DIR}/../SupportSharedLib.cmake")
endif()

# We build libraries into WASM_LIBRARY_DIR, so lets tell CMake
# to find libraries from there.
if (NOT "$ENV{WASM_LIBRARY_DIR}" STREQUAL "")
  list(APPEND CMAKE_FIND_ROOT_PATH "$ENV{WASM_LIBRARY_DIR}")
  set(CMAKE_INSTALL_PREFIX "$ENV{WASM_LIBRARY_DIR}" CACHE PATH
    "Install path prefix, prepended onto install directories." FORCE)
endif()

set_property(GLOBAL PROPERTY TARGET_SUPPORTS_SHARED_LIBS TRUE)
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${SIDE_MODULE_CFLAGS}")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${SIDE_MODULE_CXXFLAGS}")
set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${SIDE_MODULE_LDFLAGS}")
set(CMAKE_STATIC_LINKER_FLAGS "${CMAKE_STATIC_LINKER_FLAGS} ${SIDE_MODULE_LDFLAGS}")

# We don't want SIDE_MODULE=1 for static libraries
string(REPLACE "-sSIDE_MODULE=1" "" CMAKE_STATIC_LINKER_FLAGS "${CMAKE_STATIC_LINKER_FLAGS}")
