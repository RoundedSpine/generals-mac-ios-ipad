# GeneralsX @build Codex 25/10/2026 Controlled UIKit run-loop slice experiment for delayed touch delivery.
# Applied only by the iOS SDL FetchContent declaration. Fail rather than silently
# carrying an unreviewed patch to a different SDL implementation.
if(NOT DEFINED SDL3_SOURCE_DIR)
    message(FATAL_ERROR "SDL3_SOURCE_DIR is required")
endif()
set(_source "${SDL3_SOURCE_DIR}/src/video/uikit/SDL_uikitevents.m")
file(READ "${_source}" _contents)
set(_original [=[    // Pump most event types.
    SInt32 result;
    do {
        result = CFRunLoopRunInMode(kCFRunLoopDefaultMode, seconds, TRUE);
    } while (result == kCFRunLoopRunHandledSource);]=])
set(_replacement [=[    // GeneralsX @build Codex 25/10/2026 Experimental 1 ms default-mode slice.
    // Let the run loop continue after a source rather than returning immediately.
    // This is a requested run duration, not a timeout for individual callbacks.
    CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.001, FALSE);
    SInt32 result;]=])
string(FIND "${_contents}" "${_replacement}" _already_patched)
if(NOT _already_patched EQUAL -1)
    message(STATUS "SDL3 iOS event-pump experiment already applied")
    return()
endif()
string(FIND "${_contents}" "${_original}" _context)
if(_context EQUAL -1)
    message(FATAL_ERROR "SDL3 UIKit pump context changed; review the iOS event-pump experiment")
endif()
string(REPLACE "${_original}" "${_replacement}" _patched "${_contents}")
file(WRITE "${_source}" "${_patched}")
message(STATUS "SDL3 iOS event-pump experiment: 1 ms default run-loop slice, no return after source")
