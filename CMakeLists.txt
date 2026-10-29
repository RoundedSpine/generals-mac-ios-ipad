cmake_minimum_required(VERSION 3.25)

# Use packagename_ROOT for FindPackage.
if(POLICY CMP0074)
    cmake_policy(SET CMP0074 NEW)
endif()

# Disable default MSVC setting CRT type so we can set it ourselves.
if(POLICY CMP0091)
    cmake_policy(SET CMP0091 NEW)
endif()

# Disable default MSVC warning level so we can set it ourselves.
if(POLICY CMP0092)
    cmake_policy(SET CMP0092 NEW)
endif()

# Allow specifying MSVC debug configurations.
#if(POLICY CMP0141)
#    cmake_policy(SET CMP0141 NEW)
#endif()

set(CMAKE_MODULE_PATH ${CMAKE_MODULE_PATH} "${CMAKE_SOURCE_DIR}/cmake/")

include(FeatureSummary)
include(CMakeDependentOption)

# We don't support in tree builds, so help people make the right choice.
if (CMAKE_BINARY_DIR STREQUAL CMAKE_SOURCE_DIR)
    message(FATAL_ERROR "Building in-source is not supported! Create a build dir and remove ${CMAKE_SOURCE_DIR}/CMakeCache.txt")
endif()

# Top level project, doesn't really affect anything.
project(genzh LANGUAGES C CXX)

# GeneralsX @build Codex 26/10/2026 Optional isolated cache namespace for controlled iOS comparisons.
set(GENERALS_DXVK_CACHE_TAG "" CACHE STRING "Isolate iOS DXVK state cache using this test-build tag")
if(NOT GENERALS_DXVK_CACHE_TAG STREQUAL "")
    if(NOT GENERALS_DXVK_CACHE_TAG MATCHES "^[A-Za-z0-9_-]+$")
        message(FATAL_ERROR "GENERALS_DXVK_CACHE_TAG must contain only letters, digits, underscores or hyphens")
    endif()
    add_compile_definitions(GENERALS_DXVK_CACHE_TAG="${GENERALS_DXVK_CACHE_TAG}")
endif()

# GeneralsX @build Codex 26/10/2026 Keep the bounded serial search-context experiment opt-in.
option(GENERALS_SEARCH_CONTEXT "Use generation-stamped single-threaded Zero Hour search state" OFF)
if(GENERALS_SEARCH_CONTEXT)
    add_compile_definitions(GENERALS_SEARCH_CONTEXT=1)
endif()

# GeneralsX @build Codex 27/10/2026 Explicit occupancy queries shared by gameplay and optional diagnostics.
option(GENERALS_OCCUPANCY_WORKER "Use explicit occupancy queries with optional copied-query diagnostics" OFF)
if(GENERALS_OCCUPANCY_WORKER)
    if(NOT GENERALS_SEARCH_CONTEXT)
        message(FATAL_ERROR "GENERALS_OCCUPANCY_WORKER requires GENERALS_SEARCH_CONTEXT")
    endif()
    add_compile_definitions(GENERALS_OCCUPANCY_WORKER=1)
endif()

# GeneralsX @build Codex 27/10/2026 Historical replay diagnostics are independent of gameplay query validation.
option(GENERALS_OCCUPANCY_SHADOW_VALIDATION "Replay sampled occupancy transcripts for diagnostics" OFF)
if(GENERALS_OCCUPANCY_SHADOW_VALIDATION)
    if(NOT GENERALS_OCCUPANCY_WORKER)
        message(FATAL_ERROR "GENERALS_OCCUPANCY_SHADOW_VALIDATION requires GENERALS_OCCUPANCY_WORKER")
    endif()
    add_compile_definitions(GENERALS_OCCUPANCY_SHADOW_VALIDATION=1)
endif()
# GeneralsX @build Codex 27/10/2026 Retain the owned-route prototype without copying every main-thread route.
option(GENERALS_OWNED_PATH_ROUTE "Collect unoptimized routes before main-thread materialization" OFF)
if(GENERALS_OWNED_PATH_ROUTE)
    if(NOT GENERALS_SEARCH_CONTEXT)
        message(FATAL_ERROR "GENERALS_OWNED_PATH_ROUTE requires GENERALS_SEARCH_CONTEXT")
    endif()
    add_compile_definitions(GENERALS_OWNED_PATH_ROUTE=1)
endif()

# GeneralsX @build Codex 27/10/2026 Real ordinary-search loop handoff with frozen simulation and caller-side finalization.
option(GENERALS_EXCLUSIVE_PATH_WORKER "Run ordinary fine-search loops on one exclusive worker" OFF)
if(GENERALS_EXCLUSIVE_PATH_WORKER)
    if(NOT GENERALS_SEARCH_CONTEXT)
        message(FATAL_ERROR "GENERALS_EXCLUSIVE_PATH_WORKER requires GENERALS_SEARCH_CONTEXT")
    endif()
    add_compile_definitions(GENERALS_EXCLUSIVE_PATH_WORKER=1)
endif()
# GeneralsX @feature Codex 27/10/2026 Two queued requests with bounded per-phase contexts, main participation and validated ordered reuse.
option(GENERALS_PARALLEL_PATH_BATCH "Enable experimental two-request parallel ordinary, escape, closest and failure-fallback searches" OFF)
if(GENERALS_PARALLEL_PATH_BATCH)
    if(NOT GENERALS_EXCLUSIVE_PATH_WORKER OR NOT GENERALS_OCCUPANCY_WORKER)
        message(FATAL_ERROR "GENERALS_PARALLEL_PATH_BATCH requires both path worker options")
    endif()
    add_compile_definitions(GENERALS_PARALLEL_PATH_BATCH=1)
endif()

# GeneralsX @performance Codex 30/10/2026 Keep minimum-label zone merging opt-in for matched native testing.
option(GENERALS_FAST_ZONE_MERGES "Use minimum-root equivalence merging during Zero Hour zone rebuilds" OFF)
if(GENERALS_FAST_ZONE_MERGES)
    add_compile_definitions(GENERALS_FAST_ZONE_MERGES=1)
endif()

# GeneralsX @feature Codex 29/10/2026 Complete speculative APIs own hierarchy, engine Paths and optimization through joined validation.
option(GENERALS_COMPLETE_PATH_WORKER "Run complete queued search APIs on parallel participants" OFF)
if(GENERALS_COMPLETE_PATH_WORKER)
    if(NOT GENERALS_PARALLEL_PATH_BATCH)
        message(FATAL_ERROR "GENERALS_COMPLETE_PATH_WORKER requires GENERALS_PARALLEL_PATH_BATCH")
    endif()
    add_compile_definitions(GENERALS_COMPLETE_PATH_WORKER=1)
endif()

# GeneralsX @performance Codex 30/10/2026 Benchmark request-local occupancy reuse independently from zone merging.
option(GENERALS_FROZEN_OCCUPANCY_CACHE "Reuse occupancy results only within a frozen complete search request" OFF)
if(GENERALS_FROZEN_OCCUPANCY_CACHE)
    if(NOT GENERALS_COMPLETE_PATH_WORKER)
        message(FATAL_ERROR "GENERALS_FROZEN_OCCUPANCY_CACHE requires GENERALS_COMPLETE_PATH_WORKER")
    endif()
    add_compile_definitions(GENERALS_FROZEN_OCCUPANCY_CACHE=1)
endif()

# GeneralsX @build Codex 28/10/2026 Optional phase-boundary timing for the experimental search batch.
option(GENERALS_PATH_TIMING "Summarize experimental pathfinding phase wall times at shutdown" OFF)
if(GENERALS_PATH_TIMING)
    if(NOT GENERALS_PARALLEL_PATH_BATCH)
        message(FATAL_ERROR "GENERALS_PATH_TIMING requires GENERALS_PARALLEL_PATH_BATCH")
    endif()
    add_compile_definitions(GENERALS_PATH_TIMING=1)
endif()

# GeneralsX @build Codex 26/10/2026 Gate the verified-quad conversion for experimental device testing.
option(GENERALS_QUAD_LISTS "Convert verified screen/water quads to triangle lists" OFF)
if(GENERALS_QUAD_LISTS)
    add_compile_definitions(GENERALS_QUAD_LISTS=1)
endif()
# GeneralsX @build Codex 26/10/2026 Temporary strip probes are opt-in and absent from regular builds.
option(GENERALS_STRIP_DIAGNOSTICS "Enable bounded CPU strip/index diagnostics" OFF)
if(GENERALS_STRIP_DIAGNOSTICS)
    add_compile_definitions(GENERALS_STRIP_DIAGNOSTICS=1)
endif()

# GeneralsX @build BenderAI 10/02/2026
# Linux port: Make CompatLib headers globally accessible so Core libraries (WWLib, WWMath, etc.)
# can access platform compatibility types when building for non-Windows platforms
if(UNIX)
    include_directories(${CMAKE_SOURCE_DIR}/Generals/Code/CompatLib/Include)
endif()

# Compiler cache (ccache) – must be included before compilers.cmake so the
# launcher is registered before CMake finalizes the compiler selection.
include(cmake/ccache.cmake)

# This file handles extra settings wanted/needed for different compilers.
include(cmake/compilers.cmake)

# Debug symbol stripping for Release builds (MinGW)
include(cmake/debug_strip.cmake)

include(FetchContent)

# MinGW-w64 specific configuration
if(MINGW)
    include(cmake/mingw.cmake)
    include(cmake/reactos-atl.cmake)
    include(cmake/widl.cmake)
endif()

# Find/Add build dependencies and stubs shared by all projects
if((WIN32 OR "${CMAKE_SYSTEM}" MATCHES "Windows") AND ${CMAKE_SIZEOF_VOID_P} EQUAL 4)
    include(cmake/miles.cmake)
    include(cmake/bink.cmake)
endif()

# Always include DX8 headers (needed for both Windows and Linux builds)
# On Windows: min-dx8-sdk headers
# On Linux: DXVK headers (for D3D8→Vulkan translation)
include(cmake/dx8.cmake)

# SDL3 windowing/input for Linux builds (Phase 1)
# GeneralsX @build BenderAI 11/02/2026
if(SAGE_USE_SDL3)
    include(cmake/sdl3.cmake)
endif()

# Define a dummy stlport target when not on VC6.
if (IS_VS6_BUILD)
    include(cmake/stlport.cmake)
else()
    add_library(stlport INTERFACE)
endif()

include(cmake/config.cmake)
include(cmake/gamespy.cmake)
include(cmake/lzhl.cmake)

# GeneralsX @bugfix fbraz 10/03/2026 Include openal.cmake here (before Core subdirectory)
# so OpenAL::OpenAL target is available when Core/GameEngineDevice/CMakeLists.txt processes.
# openal.cmake is self-guarded with if(SAGE_USE_OPENAL), so this is always safe to include.
include(cmake/openal.cmake)

# GeneralsX @feature BenderAI 21/04/2026 libcurl for in-game update checker (SAGE_UPDATE_CHECK builds)
# curl.cmake is self-guarded with if(SAGE_UPDATE_CHECK), so always safe to include.
include(cmake/curl.cmake)

# GeneralsX @feature fbraz 03/05/2026 Phase 4: Deterministic math library integration
# gamemath.cmake integrates fdlibm-based GameMath for cross-platform replay validation.
# Upstream reference: Okladnoj, PR #2670
# https://github.com/TheSuperHackers/GeneralsGameCode/pull/2670
# Self-guarded with if(SAGE_USE_DETERMINISTIC_MATH), so always safe to include.
include(cmake/gamemath.cmake)

if (IS_VS6_BUILD)
    # The original max sdk does not compile against a modern compiler.
    # If there is a desire to make this work, then a fixed max sdk needs to be created.
    add_subdirectory(Dependencies/MaxSDK)
endif()
add_subdirectory(Dependencies/Utility)

# To be removed when abandoning VC6
if (IS_VS6_BUILD)
    include_directories(Dependencies/Utility)
    add_compile_options(/FIUtility/CppMacros.h)
endif()

add_subdirectory(resources)

add_subdirectory(Core)

# GeneralsX @bugfix GitHubCopilot 14/04/2026 CompatLib must be configured on UNIX even when
# only Generals (not ZH) is built. It sets up d3d8lib INTERFACE includes for DXVK headers
# (windows_base.h) that core_wwcommon depends on transitively. When ZH is built,
# GeneralsMD/Code/CMakeLists.txt already includes CompatLib via add_subdirectory.
if(UNIX AND NOT RTS_BUILD_ZEROHOUR)
    add_subdirectory(GeneralsMD/Code/CompatLib)
endif()

# SagePatch (casual QoL extras: screenshot, cursor lock, brightness, etc.)
# Must be added before the game targets so sage_patch target exists when we
# declare the dependency below.
if(RTS_BUILD_OPTION_SAGE_PATCH)
    add_subdirectory(Patches/SagePatch)
endif()

# Add main build targets
if(RTS_BUILD_ZEROHOUR)
    add_subdirectory(GeneralsMD)
    if(TARGET sage_patch)
        add_dependencies(z_generals sage_patch)
    endif()
endif()

if(RTS_BUILD_GENERALS)
    add_subdirectory(Generals)
    if(TARGET sage_patch)
        add_dependencies(g_generals sage_patch)
    endif()
endif()

feature_summary(WHAT ENABLED_FEATURES DESCRIPTION "Enabled features:")
feature_summary(WHAT DISABLED_FEATURES DESCRIPTION "Disabled features:")
