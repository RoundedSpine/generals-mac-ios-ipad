# Runtime iOS memory capability diagnostics — 31 October 2026

## Scope

At the user's request, report the running process's memory entitlements in the
existing `generals-stderr.log`. The source build plist and a provisioning profile
alone cannot confirm what a sideloading tool signed into the installed app.

The iOS launcher calls the device-layer diagnostic once after stderr redirection
is ready and before engine/resource initialization. Desktop launch paths and
gameplay/search settings are unchanged. The signing/exported entitlements are
also unchanged; this feature observes them rather than granting capabilities.

## Output and limits

- `[IOS_MEMORY_ENTITLEMENTS]`: `source=running_process`, with increased-memory-limit
  and extended-virtual-addressing values of `true`, `false`, `absent`, or `unknown`.
- `[IOS_MEMORY_ENTITLEMENT_QUERY]`: each query's status and numeric CF error code.
  An unavailable API/task, query error or unexpected type never becomes `true`.
- `[IOS_MEMORY]`: current process headroom from `os_proc_available_memory`, task
  physical footprint from `TASK_VM_INFO`, and hardware RAM from `hw.memsize`,
  expressed in MiB. Failed/short footprint or hardware queries remain `unknown`.

The optional self-query resolves SecTaskCreateFromSelf and
SecTaskCopyValueForEntitlement from the system Security framework at runtime.
These symbols are not declared by the public iOS SDK, so neither is a required
link dependency. An unavailable or denied query leaves explicit unknown values
and does not abort startup. The device source links public CoreFoundation APIs,
releases returned task/value/error objects before closing its framework handle,
and lives under Core/GameEngineDevice. There are no native calls in GameLogic.

A true signed entitlement is evidence of the executing process's entitlement
value. It does not establish that iOS granted a particular jetsam limit. Process
headroom changes with policy and memory pressure; hardware RAM is a different
quantity. EVA describes virtual address space rather than extra physical RAM.
No allocation stress test, private memory-limit override, or per-frame sampling
is introduced.

## Verification

The compiled production diagnostic body passes eleven simulated API scenarios:
true/false/absent values, a returned error alongside a value, an unexpected value
type, unavailable framework/symbol/task, failed hardware/footprint queries, and
a short footprint response. It verifies output, continued memory observations,
framework closure and task/value/error release balance under `-Werror`.
That test also passes ASan/UBSan. All five startup, six callback, ten packaging
and twelve warning/build regression cases pass. The production iOS CMake source
block configures successfully with a nested project source directory.

Host stand-ins do not establish native API availability or device policy. Native
iOS SDK compilation and a new sideloaded device log remain the final validation
boundary. The initial device check should look for both entitlement values equal
to `true`, query statuses `ok`, and the separate OS memory observations.
