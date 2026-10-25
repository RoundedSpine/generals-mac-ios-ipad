# GeneralsX @build Codex 25/10/2026 Add diagnostic UIKit boundary samples without changing delivery or timestamps.
if(NOT DEFINED SDL3_SOURCE_DIR)
    message(FATAL_ERROR "SDL3_SOURCE_DIR is required")
endif()
set(_directory "${SDL3_SOURCE_DIR}/src/video/uikit")
set(_source "${_directory}/SDL_uikitview.m")
file(READ "${_source}" _contents)
set(_marker "// GeneralsX UIKit callback boundary probe v1")
string(FIND "${_contents}" "${_marker}" _already_patched)
if(_already_patched EQUAL -1)
    set(_original_implementation "@implementation SDL_uikitview")
    set(_probe [=[// GeneralsX UIKit callback boundary probe v1
// GeneralsX @feature Codex 25/10/2026 Record native clock values; event dispatch stays unchanged.
#include "GeneralsXUIKitTouchProbe.h"
static void GXRecordUIKitTouch(Uint32 type, Uint64 source, UITouch *touch, UIEvent *event,
                               Uint64 callbackNS, NSTimeInterval callbackUptime)
{
    const GXUIKitTouchProbe *probe = (const GXUIKitTouchProbe *)SDL_GetPointerProperty(
        SDL_GetGlobalProperties(), GX_UIKIT_TOUCH_PROBE_PROPERTY, NULL);
    if (probe && probe->record) {
        GXUIKitTouchSample sample;
        sample.type = type;
        sample.source_ns = source;
        sample.finger = (uint64_t)(uintptr_t)touch;
        sample.callback_ns = callbackNS;
        sample.callback_uptime = callbackUptime;
        sample.event_timestamp = event.timestamp;
        sample.touch_timestamp = touch.timestamp;
        sample.touch_kind = (int)touch.type;
        probe->record(&sample);
    }
}

@implementation SDL_uikitview]=])
    string(FIND "${_contents}" "${_original_implementation}" _context)
    if(_context EQUAL -1)
        message(FATAL_ERROR "SDL UIKit implementation context changed; review the touch probe")
    endif()
    string(REPLACE "${_original_implementation}" "${_probe}" _contents "${_contents}")

    set(_callbacks touchesBegan touchesEnded touchesCancelled touchesMoved)
    set(_types SDL_EVENT_FINGER_DOWN SDL_EVENT_FINGER_UP SDL_EVENT_FINGER_CANCELED SDL_EVENT_FINGER_MOTION)
    foreach(_index RANGE 0 3)
        list(GET _callbacks ${_index} _callback)
        list(GET _types ${_index} _type)
        set(_signature "- (void)${_callback}:(NSSet *)touches withEvent:(UIEvent *)event\n{\n")
        string(FIND "${_contents}" "${_signature}" _start)
        if(_start EQUAL -1)
            message(FATAL_ERROR "SDL UIKit callback ${_callback} context changed; review the touch probe")
        endif()
        string(REPLACE "${_signature}" "${_signature}    const Uint64 gxCallbackNS = SDL_GetTicksNS();\n    const NSTimeInterval gxCallbackUptime = NSProcessInfo.processInfo.systemUptime;\n" _contents "${_contents}")
        # Limit the rewrite to this callback; other pointer/keyboard paths stay byte-for-byte unchanged.
        string(FIND "${_contents}" "${_signature}" _start)
        string(SUBSTRING "${_contents}" ${_start} -1 _suffix)
        string(FIND "${_suffix}" "\n}\n" _end)
        if(_end EQUAL -1)
            message(FATAL_ERROR "SDL UIKit callback boundary changed")
        endif()
        math(EXPR _length "${_end} + 3")
        string(SUBSTRING "${_suffix}" 0 ${_length} _body)
        if(_index EQUAL 3)
            set(_send "SDL_SendTouchMotion")
        else()
            set(_send "SDL_SendTouch")
        endif()
        set(_original "${_send}(UIKit_GetEventTimestamp([event timestamp]),")
        string(FIND "${_body}" "${_original}" _call)
        if(_call EQUAL -1)
            message(FATAL_ERROR "SDL UIKit send context changed in ${_callback}")
        endif()
        set(_replacement "const Uint64 gxSourceNS = UIKit_GetEventTimestamp([event timestamp]);\n        GXRecordUIKitTouch(${_type}, gxSourceNS, touch, event, gxCallbackNS, gxCallbackUptime);\n        ${_send}(gxSourceNS,")
        string(REPLACE "${_original}" "${_replacement}" _patched_body "${_body}")
        string(REPLACE "${_body}" "${_patched_body}" _contents "${_contents}")
    endforeach()
    file(WRITE "${_source}" "${_contents}")
endif()
configure_file("${CMAKE_CURRENT_LIST_DIR}/../Core/Libraries/Source/WWVegas/WWLib/iosuikittouchprobe.h"
               "${_directory}/GeneralsXUIKitTouchProbe.h" COPYONLY)
message(STATUS "SDL3 iOS UIKit touch boundary probe applied; upstream event pump retained")
