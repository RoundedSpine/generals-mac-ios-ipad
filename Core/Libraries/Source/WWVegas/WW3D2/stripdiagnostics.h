#pragma once

// GeneralsX @feature Codex 26/10/2026 Temporary opt-in strip investigation; no GPU readback or rendering changes.
#ifdef GENERALS_STRIP_DIAGNOSTICS
#include <d3d8.h>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <mutex>

namespace gxstrip {
constexpr unsigned MaxDraws = 64, MaxUploads = 64, MaxSentinels = 32;
// GeneralsX @feature Codex 26/10/2026 Keep tiny water-track observations independent of mesh-upload churn.
constexpr unsigned MaxWaterUploads = 4;
constexpr uint64_t WaterScanBudget = 4096;
constexpr uint64_t ScanBudget = 4 * 1024 * 1024; // At most 8 MiB of CPU index data per process.
struct Upload {
 const void* buffer = nullptr;
 unsigned first = 0, count = 0, minimum = 0, maximum = 0, hits = 0;
 unsigned positions[MaxSentinels] = {};
 bool known = false;
};
struct DrawKey { const char* file = nullptr; const char* origin = nullptr; int line = 0; unsigned topology = 0, primitives = 0; bool indexed = false; };
struct State {
 std::mutex mutex;
 Upload uploads[MaxUploads];
 Upload waterUploads[MaxWaterUploads];
 DrawKey draws[MaxDraws];
 unsigned uploadNext = 0, drawCount = 0, indexReports = 0;
 uint64_t scanned = 0, waterScanned = 0;
 unsigned waterNext = 0, waterReports = 0;
 bool announced = false;
};
inline State& state() { static State value; return value; }
inline const char*& origin() { static thread_local const char* value = "direct"; return value; }
struct Origin {
 const char* previous;
 explicit Origin(const char* value) : previous(origin()) { origin() = value; }
 ~Origin() { origin() = previous; }
};
inline bool strip(unsigned topology) { return topology == 3 || topology == 5 || topology == 6; }
inline void announce(State& s) {
 if (s.announced) return;
 s.announced = true;
 std::fprintf(stderr, "[STRIP_DIAG] enabled draw_configs=64 upload_reports=64 scan_indices=4194304 retained_water_buffers=4 water_scan_indices=4096; timings=CPU_submission_not_isolated_pipeline_compile; DXVK_async_warning_order_not_exact\n");
}
inline void forget(const void* buffer) {
 auto& s = state(); std::lock_guard<std::mutex> lock(s.mutex);
 for (auto& u : s.uploads) if (u.buffer == buffer) u = Upload{};
 for (auto& u : s.waterUploads) if (u.buffer == buffer) u = Upload{};
}
inline void capture(const void* buffer, unsigned first, const unsigned short* indices, unsigned count, bool waterTrack = false) {
 if (!buffer) return;
 auto& s = state(); std::lock_guard<std::mutex> lock(s.mutex);
 Upload* out = nullptr;
 // Every write invalidates both tables before a fresh observation is installed.
 for (auto& u : s.uploads) if (u.buffer == buffer) u.known = false;
 for (auto& u : s.waterUploads) if (u.buffer == buffer) u.known = false;
 if (waterTrack) {
  for (auto& u : s.waterUploads) if (u.buffer == buffer) { out = &u; break; }
  if (!out) out = &s.waterUploads[s.waterNext++ % MaxWaterUploads];
 } else {
  for (auto& u : s.uploads) if (u.buffer == buffer) { out = &u; break; }
  if (!out) out = &s.uploads[s.uploadNext++ % MaxUploads];
 }
 *out = Upload{}; out->buffer = buffer; out->first = first; out->count = count;
 uint64_t& scanned = waterTrack ? s.waterScanned : s.scanned;
 const uint64_t budget = waterTrack ? WaterScanBudget : ScanBudget;
 // A newer unobserved write invalidates older knowledge, including after the scan budget expires.
 if (!indices || !count || count > budget - scanned) return;
 scanned += count; out->known = true; out->minimum = 65535;
 for (unsigned i = 0; i < count; ++i) {
  unsigned value = indices[i];
  if (value < out->minimum) out->minimum = value;
  if (value > out->maximum) out->maximum = value;
  if (value == 65535) {
   if (out->hits < MaxSentinels) out->positions[out->hits] = i;
   ++out->hits;
  }
 }
 if (waterTrack && s.waterReports < 16) {
  announce(s); ++s.waterReports;
  std::fprintf(stderr, "[STRIP_WATER_UPLOAD] buffer=%p first=%u count=%u min=%u max=%u sentinel16=%u observation=retained_CPU_upload water_scanned=%llu\n",
   buffer, first, count, out->minimum, out->maximum, out->hits,
   static_cast<unsigned long long>(s.waterScanned));
 }
 if (out->hits && s.indexReports < MaxUploads) {
  announce(s); ++s.indexReports;
  std::fprintf(stderr, "[STRIP_INDEX] buffer=%p upload_first=%u upload_count=%u min=%u max=%u sentinel16=%u first_sentinel=%llu scope=upload_not_proof_of_strip_use\n",
   buffer, first, count, out->minimum, out->maximum, out->hits,
   static_cast<unsigned long long>(uint64_t(first) + out->positions[0]));
 }
}
struct Sample { unsigned id = 0; };
inline Sample reserve(const char* file, int line, unsigned topology, unsigned primitives, bool indexed) {
 if (!strip(topology)) return {};
 auto& s = state(); std::lock_guard<std::mutex> lock(s.mutex);
 for (unsigned i = 0; i < s.drawCount; ++i) {
  const auto& d = s.draws[i];
  if (d.line == line && d.topology == topology && d.primitives == primitives && d.indexed == indexed &&
      std::strcmp(d.file, file) == 0 && std::strcmp(d.origin, origin()) == 0) return {};
 }
 if (s.drawCount == MaxDraws) return {};
 announce(s);
 s.draws[s.drawCount++] = {file, origin(), line, topology, primitives, indexed};
 return {s.drawCount};
}
inline void describe(Sample sample, const char* file, int line, const char* function,
 unsigned topology, unsigned primitives, bool indexed, const void* buffer, unsigned start, unsigned base,
 unsigned minVertex, unsigned vertices) {
 auto& s = state(); std::lock_guard<std::mutex> lock(s.mutex);
 const Upload* u = nullptr;
 const char* observation = "unavailable";
 for (auto& entry : s.uploads) if (buffer && entry.buffer == buffer) { u = &entry; observation = "latest_upload"; break; }
 for (auto& entry : s.waterUploads) if (buffer && entry.buffer == buffer && entry.known) { u = &entry; observation = "retained_water_upload"; break; }
 uint64_t count = uint64_t(primitives) + (topology == 3 ? 1 : 2);
 const char* status = indexed ? "unknown" : "not_indexed";
 unsigned hits = 0;
 if (indexed && u && u->known && start >= u->first && uint64_t(start) + count <= uint64_t(u->first) + u->count) {
  for (unsigned i = 0; i < u->hits && i < MaxSentinels; ++i) {
   uint64_t position = uint64_t(u->first) + u->positions[i];
   if (position >= start && position < uint64_t(start) + count) ++hits;
  }
  status = hits ? "present" : (u->hits > MaxSentinels ? "unknown_truncated" : "absent");
 }
 std::fprintf(stderr, "[STRIP_DRAW_BEGIN] id=%u source=%s:%d function=%s origin=%s topology=%u indexed=%d primitives=%u buffer=%p start=%u index_count=%llu base=%u min_vertex=%u vertices=%u sentinel16=%s hits_observed=%u upload_min=%u upload_max=%u observation=%s range_scope=latest_CPU_upload\n",
  sample.id, file, line, function, origin(), topology, indexed, primitives, buffer, start,
  static_cast<unsigned long long>(count), base, minVertex, vertices, status, hits,
  u && u->known ? u->minimum : 0, u && u->known ? u->maximum : 0, observation);
}
template<class Device, class Call>
auto draw(Device* device, const char* file, int line, const char* function, unsigned topology,
 unsigned primitives, bool indexed, unsigned start, unsigned minVertex, unsigned vertices, Call call) -> decltype(call()) {
 auto sample = reserve(file, line, topology, primitives, indexed);
 if (!sample.id) return call();
 IDirect3DIndexBuffer8* buffer = nullptr;
 unsigned base = 0;
 if (indexed) device->GetIndices(&buffer, &base); // CPU state query, bounded to sampled draws; returns a reference.
 describe(sample, file, line, function, topology, primitives, indexed, buffer, start, base, minVertex, vertices);
 if (buffer) buffer->Release();
 auto begin = std::chrono::steady_clock::now();
 auto result = call();
 double ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - begin).count();
 std::fprintf(stderr, "[STRIP_DRAW_END] id=%u submit_ms=%.3f result=%ld timing_scope=CPU_call_not_GPU_or_isolated_pipeline_compile\n", sample.id, ms, static_cast<long>(result));
 return result;
}
}
#define GX_STRIP_UP(device, topology, primitives, data, stride) \
 gxstrip::draw((device), __FILE__, __LINE__, __func__, (topology), (primitives), false, 0, 0, 0, \
 [&]() { return (device)->DrawPrimitiveUP((topology), (primitives), (data), (stride)); })
#define GX_STRIP_INDEXED(device, topology, minimum, vertices, start, primitives) \
 gxstrip::draw((device), __FILE__, __LINE__, __func__, (topology), (primitives), true, (start), (minimum), (vertices), \
 [&]() { return (device)->DrawIndexedPrimitive((topology), (minimum), (vertices), (start), (primitives)); })
#define GX_STRIP_CAPTURE(buffer, first, indices, count) gxstrip::capture((buffer), (first), (indices), (count))
#define GX_STRIP_WATER_CAPTURE(buffer, first, indices, count) gxstrip::capture((buffer), (first), (indices), (count), true)
#define GX_STRIP_FORGET(buffer) gxstrip::forget(buffer)
#define GX_STRIP_ORIGIN(name) gxstrip::Origin gxStripOriginScope(name)
#else
#define GX_STRIP_UP(device, topology, primitives, data, stride) (device)->DrawPrimitiveUP((topology), (primitives), (data), (stride))
#define GX_STRIP_INDEXED(device, topology, minimum, vertices, start, primitives) (device)->DrawIndexedPrimitive((topology), (minimum), (vertices), (start), (primitives))
#define GX_STRIP_CAPTURE(buffer, first, indices, count) ((void)0)
#define GX_STRIP_WATER_CAPTURE(buffer, first, indices, count) ((void)0)
#define GX_STRIP_FORGET(buffer) ((void)0)
#define GX_STRIP_ORIGIN(name) ((void)0)
#endif
