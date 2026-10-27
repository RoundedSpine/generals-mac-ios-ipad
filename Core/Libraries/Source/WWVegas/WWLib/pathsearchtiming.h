#pragma once
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>

// GeneralsX @feature Codex 28/10/2026 Measure phase boundaries without per-cell clocks, allocation or concurrent shared counters.
template<class Clock = std::chrono::steady_clock>
class BasicPathSearchTiming {
public:
 enum Phase { Queue, Preparation, CallerPreparation, Pair, WorkerKernel, CallerKernel, SerialKernel, Validation, Hierarchy, Finalization, PhaseCount };
 struct Metric {
  std::uint64_t calls=0, totalNanoseconds=0, maxNanoseconds=0;
  std::array<std::uint64_t,6> thresholds{};
  void record(std::uint64_t ns) {
   ++calls;totalNanoseconds+=ns;if(ns>maxNanoseconds) maxNanoseconds=ns;
   const std::uint64_t milliseconds[6]={1,5,20,50,100,500};
   for(unsigned i=0;i<6;++i) if(ns>=milliseconds[i]*1000000) ++thresholds[i];
  }
  void merge(const Metric& other) {
   calls+=other.calls;totalNanoseconds+=other.totalNanoseconds;
   if(other.maxNanoseconds>maxNanoseconds) maxNanoseconds=other.maxNanoseconds;
   for(unsigned i=0;i<6;++i) thresholds[i]+=other.thresholds[i];
  }
 };
 // Noncopyable, optional and explicitly stoppable so preparation excludes the parallel barrier.
 class Scope {
  Metric* m_metric;
  typename Clock::time_point m_start{};
 public:
  explicit Scope(Metric* metric):m_metric(metric) {if(m_metric) m_start=Clock::now();}
  Scope(const Scope&)=delete;
  Scope& operator=(const Scope&)=delete;
  ~Scope(){stop();}
  void stop() {
   if(!m_metric) return;
   const auto elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-m_start).count();
   m_metric->record(elapsed>0?static_cast<std::uint64_t>(elapsed):0);
   m_metric=nullptr;
  }
 };
 Metric& operator[](Phase phase){return m_metrics[phase];}
 const Metric& operator[](Phase phase)const{return m_metrics[phase];}
 void report(FILE* output)const {
  const char* names[PhaseCount]={"queue","prepare","caller_prepare","pair","worker_kernel","caller_kernel","serial_kernel","validate","hierarchy","finalize"};
  std::fprintf(output,"[PATH_TIMING] clock=steady unit=ms totals=overlapping kernels=task_wall_time thresholds=cumulative\n");
  for(unsigned i=0;i<PhaseCount;++i) {
   const auto& metric=m_metrics[i];
   std::fprintf(output,"[PATH_TIMING] phase=%s calls=%llu total_ms=%.3f max_ms=%.3f ge_1ms=%llu ge_5ms=%llu ge_20ms=%llu ge_50ms=%llu ge_100ms=%llu ge_500ms=%llu\n",
    names[i],static_cast<unsigned long long>(metric.calls),metric.totalNanoseconds/1000000.0,metric.maxNanoseconds/1000000.0,
    static_cast<unsigned long long>(metric.thresholds[0]),static_cast<unsigned long long>(metric.thresholds[1]),
    static_cast<unsigned long long>(metric.thresholds[2]),static_cast<unsigned long long>(metric.thresholds[3]),
    static_cast<unsigned long long>(metric.thresholds[4]),static_cast<unsigned long long>(metric.thresholds[5]));
  }
 }
private:
 std::array<Metric,PhaseCount> m_metrics{};
};
using PathSearchTiming=BasicPathSearchTiming<>;
