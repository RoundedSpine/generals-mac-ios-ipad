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

The first native attempt (41174187262, a67f255) passed regular/race checks and
configuration/SDL, but failed in the earlier DXVK warning adapter before the
engine build completed. That separate template fix is recorded in
IOS_BUILD_WARNING_CLEANUP_2026-10-31.md. The runtime memory report still requires
a successful replacement IPA and the user's device log.

## Long-session device evidence and sampling follow-up

The uploaded log for ~44666f8 reports increased_memory_limit=absent and
extended_virtual_addressing=absent, both with query status ok/error 0. Startup
headroom is 3304.0 MiB, footprint 72.0 MiB, and hardware RAM 7622.1 MiB. The user
reports a crash after nearly an hour and no matching IPS/Jetsam report. The game
log has no fatal stack or normal shutdown summary, and its final display-busy
messages do not establish the failing operation. There is no late-session memory
measurement. Memory pressure is a hypothesis, not a confirmed termination cause.
The preceding native build 41189741446 succeeded; the separate warning report
shows three remaining diagnostics (two template-name-table and one duplicate
archive warning), rather than a warning-free claim.

Add a snapshot on the first native iteration and then every 30 seconds, using
SDL uptime. Off-main SDL_EVENT_LOW_MEMORY delivery increments an atomic count;
main-thread event delivery samples immediately for the first warning, and main
iteration consumes pending warnings. Further warnings coalesce to at most one
sample per second while preserving the count. Periodic sampling does not catch
up in bursts after suspension. Clock rewind rebases the sampling deadline.

All snapshot OS reads and stream writes occur on the main thread. Skipped polls
perform no OS queries, and runtime snapshots never resolve Security symbols or
re-query entitlements. Capture low-rate memory rows after the general 8 MiB
spam cap as well, to retain evidence from late in long sessions. There is no
allocation probe, sampling thread, cache purge or gameplay/search adjustment.
An abrupt memory kill may still provide no warning or final snapshot.

Five startup, six callback and ten packaging cases pass. The production memory
body also passes Clang frontend and ASan/UBSan checks. Extended cases verify
cross-thread warning increments, immediate first warning, count-preserving
throttling, 30-second boundaries, no catchup/rewind underflow, and absence of
OS/private-entitlement queries between snapshots. Callback tests verify that
off-main warnings defer sampling and main-thread warnings request it without
duplicating event delivery. Native SDK and long-session device validation remain
pending. Manual SideStore entitlement editing is documented separately; the
attached two-key plist is valid but is not applied by copying it to Documents.
