# Support both standalone smoke testing and inclusion from the main engine.
if(CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR)
  cmake_minimum_required(VERSION 3.24)
  project(GXMetalBootstrap LANGUAGES CXX OBJCXX)
endif()
# Standalone native Metal proof-of-concept library.
# Does not alter the DXVK-backed d3d8lib target.
if(NOT APPLE)
  message(FATAL_ERROR "Metal backend requires an Apple target")
endif()
enable_language(OBJCXX)
add_library(gx_metal_bootstrap STATIC MetalD3D8Bootstrap.mm)
target_include_directories(gx_metal_bootstrap PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_features(gx_metal_bootstrap PUBLIC cxx_std_17)
target_link_libraries(gx_metal_bootstrap PUBLIC
  "-framework Foundation"
  "-framework Metal"
  "-framework QuartzCore"
)
if(CMAKE_SYSTEM_NAME STREQUAL "iOS")
  target_link_libraries(gx_metal_bootstrap PUBLIC "-framework UIKit")
endif()

add_library(gx_d3d8_factory SHARED MetalD3D8Factory.cpp)
target_compile_features(gx_d3d8_factory PRIVATE cxx_std_17)

option(GX_METAL_SMOKE_TESTS "Build standalone Metal bootstrap smoke tests" OFF)
if(GX_METAL_SMOKE_TESTS)
  enable_testing()
  add_executable(gx_factory_export_probe tests/FactoryExportProbe.cpp)
  target_link_libraries(gx_factory_export_probe PRIVATE gx_d3d8_factory)
  add_test(NAME d3d8_factory_export_fail_closed COMMAND gx_factory_export_probe)
  add_executable(gx_factory_lifetime_probe tests/FactoryLifetimeProbe.cpp)
  add_test(NAME factory_reference_lifetime COMMAND gx_factory_lifetime_probe)
  add_executable(gx_metal_smoke tests/MetalBootstrapSmoke.mm)
  target_link_libraries(gx_metal_smoke PRIVATE gx_metal_bootstrap)
  add_test(NAME metal_bootstrap_create_resize_destroy COMMAND gx_metal_smoke)
  set_tests_properties(metal_bootstrap_create_resize_destroy PROPERTIES SKIP_RETURN_CODE 77)
endif()
