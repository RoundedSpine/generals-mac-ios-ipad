# GeneralsX @build Codex 31/10/2026 Apply reviewed pinned dependency fixes, accepting only clean or already-patched sources.
if(NOT EXISTS "${PATCH_FILE}" OR NOT IS_DIRECTORY "${SOURCE_DIR}")
    message(FATAL_ERROR "Dependency patch requires an existing PATCH_FILE and SOURCE_DIR")
endif()
find_package(Git REQUIRED QUIET)
set(patch_command "${CMAKE_COMMAND}" -E env "GIT_CEILING_DIRECTORIES=${SOURCE_DIR}"
    "${GIT_EXECUTABLE}" -C "${SOURCE_DIR}" apply)
execute_process(COMMAND ${patch_command} --reverse --check "${PATCH_FILE}"
    RESULT_VARIABLE already_patched OUTPUT_QUIET ERROR_QUIET)
if(already_patched EQUAL 0)
    return()
endif()
execute_process(COMMAND ${patch_command} --check "${PATCH_FILE}"
    RESULT_VARIABLE can_patch OUTPUT_VARIABLE check_output ERROR_VARIABLE check_error)
if(NOT can_patch EQUAL 0)
    message(FATAL_ERROR "Pinned dependency patch does not match: ${PATCH_FILE}\n${check_output}${check_error}")
endif()
execute_process(COMMAND ${patch_command} "${PATCH_FILE}"
    RESULT_VARIABLE applied OUTPUT_VARIABLE patch_output ERROR_VARIABLE patch_error)
if(NOT applied EQUAL 0)
    message(FATAL_ERROR "Failed to apply dependency patch: ${PATCH_FILE}\n${patch_output}${patch_error}")
endif()
