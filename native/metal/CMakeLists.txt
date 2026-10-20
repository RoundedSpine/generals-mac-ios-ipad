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

option(GX_METAL_SMOKE_TESTS "Build standalone Metal bootstrap smoke tests" OFF)
if(GX_METAL_SMOKE_TESTS)
  enable_testing()
  add_executable(gx_metal_smoke tests/MetalBootstrapSmoke.mm)
  target_link_libraries(gx_metal_smoke PRIVATE gx_metal_bootstrap)
  add_test(NAME metal_bootstrap_create_resize_destroy COMMAND gx_metal_smoke)
  set_tests_properties(metal_bootstrap_create_resize_destroy PROPERTIES SKIP_RETURN_CODE 77)
endif()
