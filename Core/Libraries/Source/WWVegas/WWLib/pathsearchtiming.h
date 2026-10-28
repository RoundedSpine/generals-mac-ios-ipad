#pragma once
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cassert>
#include "pathsearchprediction.h"

// GeneralsX @feature Codex 28/10/2026 Measure phase boundaries without per-cell clocks, allocation or concurrent shared counters.
template<class Clock = std::chrono::steady_clock>
class BasicPathSearchTiming {
public:
 BasicPathSearchTiming()=default;
 BasicPathSearchTiming(const BasicPathSearchTiming&)=delete;
 BasicPathSearchTiming& operator=(const BasicPathSearchTiming&)=delete;
 enum Phase { Queue, Preparation, CallerPreparation, Pair, WorkerKernel, CallerKernel, SerialKernel, Validation, Hierarchy, Finalization, PhaseCount };
 enum class Kind { Ordinary, Safe, Closest, Count };
 // GeneralsX @feature Codex 28/10/2026 Main-thread terminal outcomes explain retained work without retaining engine handles.
 enum class Result { NotRun, Pending, Validated, Reused, Rejected, Discarded, Unfinished, Count };
 enum class Rejection {
  None, Object, Locomotor, From, To, Kind, Repulsors, ClosestPolicy, FallbackPath,
  WorldEpoch, Lifecycle, Paused, Admission, IgnoredObstacle, Tunneling,
  StartCell, GoalCell, StartIndex, Movement, Overflow, FixedMode, Recovery,
  Cells, Corridor, Occupancy, Height, Count
 };
 enum class Admission {
  Dispatched, ExistingPair, ExistingAttempt, Unavailable, Debug, Paused, Nested, ShortQueue,
  Duplicate, MissingObject, MissingAI, Dozer, CrusherKey, Prediction, Capture,
  EnvironmentFailure, ThreadFailure, AllocationFailure, Exception, DebugBuild, Count
 };
 static constexpr unsigned retainedSamples=4;
 struct ResultSample {Result result=Result::NotRun;Rejection reason=Rejection::None;};
 struct ReadSample {
  std::uint64_t queries=0,queryObservations=0,heights=0,heightObservations=0;
  unsigned flags=0;
 };
 struct TaskSample {
  Kind kind=Kind::Ordinary;
  bool primary=false, fallback=false;
  std::uint64_t nanoseconds=0;
  unsigned examined=0, fallbackExamined=0, records=0, fallbackRecords=0;
  ResultSample primaryOutcome, fallbackOutcome;
  ReadSample primaryReads,fallbackReads;
 };
 struct PairSample {
  std::uint64_t nanoseconds=0, id=0, queue=0;
  std::array<TaskSample,2> tasks{};
 };
 struct QueueSample {
  std::uint64_t nanoseconds=0, id=0;
  unsigned depth=0, entries=0, callbacks=0, charged=0;
  bool zones=false, completed=false;
  std::array<std::uint64_t,PhaseCount> phaseNanoseconds{}, phaseCalls{};
  std::array<std::uint64_t,3> serialKinds{};
 };
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
  std::uint64_t m_elapsed=0;
 public:
  explicit Scope(Metric* metric):m_metric(metric) {if(m_metric) m_start=Clock::now();}
  Scope(const Scope&)=delete;
  Scope& operator=(const Scope&)=delete;
  ~Scope(){stop();}
  std::uint64_t stop() {
   if(!m_metric) return m_elapsed;
   const auto elapsed=std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now()-m_start).count();
   m_elapsed=elapsed>0?static_cast<std::uint64_t>(elapsed):0;
   m_metric->record(m_elapsed);
   m_metric=nullptr;
   return m_elapsed;
  }
 };
 // One terminal outcome per preparation call. Slot details are supplementary, not extra attempts.
 class AdmissionScope {
  BasicPathSearchTiming& m_owner;
 public:
  Admission reason=Admission::Exception;
  int slot=-1;
  PathPredictionReason prediction=PathPredictionReason::Accepted;
  explicit AdmissionScope(BasicPathSearchTiming& owner):m_owner(owner){}
  AdmissionScope(const AdmissionScope&)=delete;
  AdmissionScope& operator=(const AdmissionScope&)=delete;
  ~AdmissionScope(){
   ++m_owner.m_admission[static_cast<unsigned>(reason)];
   if(reason==Admission::Prediction && slot>=0 && slot<2)
    ++m_owner.m_prediction[slot][static_cast<unsigned>(prediction)];
  }
 };
 // Queue snapshots contain scalars only; nested calls restore their previous stack-owned snapshot.
 class QueueScope {
  BasicPathSearchTiming& m_owner;
  QueueSample* m_previous;
  Scope m_timer;
  std::array<std::uint64_t,PhaseCount> m_beforeNanoseconds,m_beforeCalls;
  bool m_enabled;
 public:
  QueueSample sample;
  QueueScope(BasicPathSearchTiming& owner, unsigned depth):m_owner(owner),m_previous(owner.m_activeQueue),
   m_timer(depth?&owner[Queue]:nullptr),m_enabled(depth!=0) {
   if(m_enabled){
    for(unsigned i=0;i<PhaseCount;++i){m_beforeNanoseconds[i]=owner.m_metrics[i].totalNanoseconds;m_beforeCalls[i]=owner.m_metrics[i].calls;}
    sample.id=++owner.m_queueId;sample.depth=depth;owner.m_activeQueue=&sample;
   }
  }
  QueueScope(const QueueScope&)=delete;
  QueueScope& operator=(const QueueScope&)=delete;
  ~QueueScope(){
   if(!m_enabled)return;
   sample.nanoseconds=m_timer.stop();
   for(unsigned i=0;i<PhaseCount;++i){
    sample.phaseNanoseconds[i]=m_owner.m_metrics[i].totalNanoseconds-m_beforeNanoseconds[i];
    sample.phaseCalls[i]=m_owner.m_metrics[i].calls-m_beforeCalls[i];
   }
   m_owner.m_activeQueue=m_previous;
   retain(m_owner.m_slowQueues,m_owner.m_slowQueueCount,sample);
  }
 };
 class SerialScope {
  Scope m_timer;
 public:
  SerialScope(BasicPathSearchTiming& owner,bool enabled,Kind kind):m_timer(enabled?&owner[SerialKernel]:nullptr){
   if(enabled){
    ++owner.m_serialKinds[static_cast<unsigned>(kind)];
    if(owner.m_activeQueue)++owner.m_activeQueue->serialKinds[static_cast<unsigned>(kind)];
   }
  }
 };
 void captureFailure(unsigned slot,Kind kind,bool immobile,bool oldPath){
  ++m_capture[slot][static_cast<unsigned>(kind)];
  if(immobile)++m_captureImmobile[slot];
  if(oldPath)++m_captureOldPath[slot];
 }
 std::uint64_t recordPair(PairSample sample){
  sample.id=m_metrics[Pair].calls;sample.queue=m_activeQueue?m_activeQueue->id:0;
  for(auto& task:sample.tasks){
   task.primaryOutcome.result=task.primary?Result::Pending:Result::NotRun;
   task.fallbackOutcome.result=task.fallback?Result::Pending:Result::NotRun;
  }
  retain(m_slowPairs,m_slowPairCount,sample);
  return sample.id;
 }
 // The owning joined job calls once per executed phase, even if this pair was evicted from the top four.
 void resolveResult(std::uint64_t pair,unsigned role,bool fallback,Result result,Rejection reason){
  assert(role<2 && (result==Result::Reused || result==Result::Rejected || result==Result::Discarded || result==Result::Unfinished));
  assert((result==Result::Rejected)==(reason!=Rejection::None));
  ++m_results[unsigned(fallback)][static_cast<unsigned>(result)];
  if(result==Result::Rejected)++m_rejections[unsigned(fallback)][static_cast<unsigned>(reason)];
  for(unsigned i=0;i<m_slowPairCount;++i)if(m_slowPairs[i].id==pair){
   auto& task=m_slowPairs[i].tasks[role];
   (fallback?task.fallbackOutcome:task.primaryOutcome)={result,reason};
   break;
  }
 }
 std::uint64_t results(bool fallback,Result result)const{return m_results[unsigned(fallback)][static_cast<unsigned>(result)];}
 std::uint64_t rejections(bool fallback,Rejection reason)const{return m_rejections[unsigned(fallback)][static_cast<unsigned>(reason)];}
 const std::array<QueueSample,retainedSamples>& slowQueues()const{return m_slowQueues;}
 const std::array<PairSample,retainedSamples>& slowPairs()const{return m_slowPairs;}
 unsigned slowQueueCount()const{return m_slowQueueCount;}
 unsigned slowPairCount()const{return m_slowPairCount;}
 std::uint64_t admissions(Admission reason)const{return m_admission[static_cast<unsigned>(reason)];}
 std::uint64_t predictions(unsigned slot,PathPredictionReason reason)const{return m_prediction[slot][static_cast<unsigned>(reason)];}
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
  const char* admissions[]={"dispatched","existing_pair","existing_unexecuted","unavailable","debug","paused","nested","short_queue","duplicate","missing_object","missing_ai","dozer","crusher_key","prediction","capture","environment_failure","thread_failure","allocation_failure","exception","debug_build"};
  std::uint64_t attempts=0;for(auto count:m_admission)attempts+=count;
  std::fprintf(output,"[PATH_PAIR_ADMISSION] calls=%llu",u(attempts));
  for(unsigned i=0;i<m_admission.size();++i)std::fprintf(output," %s=%llu",admissions[i],u(m_admission[i]));
  std::fprintf(output,"\n");
  const char* predictions[]={"accepted","not_waiting","safe","approach","attack","blocked","nonfinal","quick","production_exit","outside_extent"};
  for(unsigned slot=0;slot<2;++slot){
   std::fprintf(output,"[PATH_PAIR_PREDICTION] slot=%u",slot);
   for(unsigned i=0;i<m_prediction[slot].size();++i)std::fprintf(output," %s=%llu",predictions[i],u(m_prediction[slot][i]));
   std::fprintf(output,"\n[PATH_PAIR_CAPTURE] slot=%u ordinary=%llu safe=%llu closest=%llu immobile=%llu old_path=%llu\n",slot,
    u(m_capture[slot][0]),u(m_capture[slot][1]),u(m_capture[slot][2]),u(m_captureImmobile[slot]),u(m_captureOldPath[slot]));
  }
  std::fprintf(output,"[PATH_SERIAL_KINDS] ordinary=%llu safe=%llu closest=%llu\n",u(m_serialKinds[0]),u(m_serialKinds[1]),u(m_serialKinds[2]));
  for(unsigned phase=0;phase<2;++phase){
   std::fprintf(output,"[PATH_RESULT_OUTCOMES] phase=%s reused=%llu rejected=%llu discarded=%llu validated_unfinished=%llu\n",
    phase?"fallback":"primary",u(results(phase,Result::Reused)),u(results(phase,Result::Rejected)),
    u(results(phase,Result::Discarded)),u(results(phase,Result::Unfinished)));
   std::fprintf(output,"[PATH_RESULT_REJECTIONS] phase=%s",phase?"fallback":"primary");
   for(unsigned i=1;i<static_cast<unsigned>(Rejection::Count);++i)
    std::fprintf(output," %s=%llu",rejectionName(static_cast<Rejection>(i)),u(m_rejections[phase][i]));
   std::fprintf(output,"\n");
  }
  for(unsigned i=0;i<m_slowQueueCount;++i){
   const auto&s=m_slowQueues[i];
   std::fprintf(output,"[PATH_QUEUE_SLOW] rank=%u queue=%llu ms=%.3f depth=%u entries=%u callbacks=%u charged=%u zones=%u completed=%u pairs=%llu serial=%llu ordinary=%llu safe=%llu closest=%llu prepare_ms=%.3f pair_ms=%.3f serial_ms=%.3f validate_ms=%.3f hierarchy_ms=%.3f finalize_ms=%.3f\n",
    i+1,u(s.id),s.nanoseconds/1000000.0,s.depth,s.entries,s.callbacks,s.charged,unsigned(s.zones),unsigned(s.completed),
    u(s.phaseCalls[Pair]),u(s.phaseCalls[SerialKernel]),u(s.serialKinds[0]),u(s.serialKinds[1]),u(s.serialKinds[2]),
    s.phaseNanoseconds[Preparation]/1000000.0,s.phaseNanoseconds[Pair]/1000000.0,s.phaseNanoseconds[SerialKernel]/1000000.0,
    s.phaseNanoseconds[Validation]/1000000.0,s.phaseNanoseconds[Hierarchy]/1000000.0,s.phaseNanoseconds[Finalization]/1000000.0);
  }
  for(unsigned i=0;i<m_slowPairCount;++i){
   const auto&s=m_slowPairs[i];
   std::fprintf(output,"[PATH_PAIR_SLOW] rank=%u pair=%llu queue=%llu ms=%.3f",i+1,u(s.id),u(s.queue),s.nanoseconds/1000000.0);
   for(unsigned j=0;j<2;++j){const auto&t=s.tasks[j];const char*role=j?"worker":"caller";
    std::fprintf(output," %s_kind=%s %s_primary=%u %s_fallback=%u %s_kernel_ms=%.3f %s_examined=%u %s_fallback_examined=%u %s_records=%u %s_fallback_records=%u",
     role,kindName(t.kind),role,unsigned(t.primary),role,unsigned(t.fallback),role,t.nanoseconds/1000000.0,
     role,t.examined,role,t.fallbackExamined,role,t.records,role,t.fallbackRecords);
    std::fprintf(output," %s_primary_result=%s %s_primary_reason=%s %s_fallback_result=%s %s_fallback_reason=%s",
     role,resultName(t.primaryOutcome.result),role,rejectionName(t.primaryOutcome.reason),
     role,resultName(t.fallbackOutcome.result),role,rejectionName(t.fallbackOutcome.reason));
   }
   std::fprintf(output,"\n");
   for(unsigned j=0;j<2;++j){const auto&t=s.tasks[j];const char*role=j?"worker":"caller";
    if(t.primary)reportReads(output,s.id,role,"primary",t.primaryReads);
    if(t.fallback)reportReads(output,s.id,role,"fallback",t.fallbackReads);
   }
  }
 }
private:
 static void reportReads(FILE* output,std::uint64_t pair,const char*role,const char*phase,const ReadSample& s){
  std::fprintf(output,"[PATH_READS_SLOW] pair=%llu role=%s phase=%s queries=%llu query_observations=%llu heights=%llu height_observations=%llu flags=%u\n",
   u(pair),role,phase,u(s.queries),u(s.queryObservations),u(s.heights),u(s.heightObservations),s.flags);
 }
 static unsigned long long u(std::uint64_t value){return static_cast<unsigned long long>(value);}
 static const char* kindName(Kind kind){return kind==Kind::Safe?"safe":kind==Kind::Closest?"closest":"ordinary";}
 static const char* resultName(Result result){
  const char* names[]={"not_run","pending","validated","reused","rejected","discarded","validated_unfinished"};
  static_assert(sizeof(names)/sizeof(*names)==static_cast<unsigned>(Result::Count),"result names must match enum");
  return names[static_cast<unsigned>(result)];
 }
 static const char* rejectionName(Rejection reason){
  const char* names[]={"none","object","locomotor","from","to","kind","repulsors","closest_policy","fallback_path",
   "world_epoch","lifecycle","paused","permanent_admission","ignored_obstacle","tunneling","start_cell","goal_cell",
   "start_index","movement","overflow","fixed_mode","recovery","cell_dependencies","corridor_dependencies","occupancy","height"};
  static_assert(sizeof(names)/sizeof(*names)==static_cast<unsigned>(Rejection::Count),"rejection names must match enum");
  return names[static_cast<unsigned>(reason)];
 }
 template<class Sample>static void retain(std::array<Sample,retainedSamples>& samples,unsigned& count,const Sample& sample){
  unsigned at=0;while(at<count&&samples[at].nanoseconds>=sample.nanoseconds)++at;
  if(at==retainedSamples)return;
  unsigned end=count<retainedSamples?count++:retainedSamples-1;
  for(unsigned i=end;i>at;--i)samples[i]=samples[i-1];samples[at]=sample;
 }
 std::array<Metric,PhaseCount> m_metrics{};
 std::array<std::uint64_t,static_cast<unsigned>(Admission::Count)> m_admission{};
 std::array<std::array<std::uint64_t,static_cast<unsigned>(PathPredictionReason::Count)>,2> m_prediction{};
 std::array<std::array<std::uint64_t,3>,2> m_capture{};
 std::array<std::uint64_t,2> m_captureImmobile{},m_captureOldPath{};
 std::array<std::uint64_t,3> m_serialKinds{};
 std::array<std::array<std::uint64_t,static_cast<unsigned>(Result::Count)>,2> m_results{};
 std::array<std::array<std::uint64_t,static_cast<unsigned>(Rejection::Count)>,2> m_rejections{};
 std::array<QueueSample,retainedSamples> m_slowQueues{};
 std::array<PairSample,retainedSamples> m_slowPairs{};
 unsigned m_slowQueueCount=0,m_slowPairCount=0;
 std::uint64_t m_queueId=0;
 QueueSample* m_activeQueue=nullptr;
};
using PathSearchTiming=BasicPathSearchTiming<>;
