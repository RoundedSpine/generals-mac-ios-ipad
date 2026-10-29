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
 // GeneralsX @feature Codex 29/10/2026 Separate fine work and full-map zone passes while preserving existing metric indices.
 enum Phase { Queue, Preparation, CallerPreparation, Pair, WorkerKernel, CallerKernel, SerialKernel, Validation, Hierarchy, Finalization,
  FineSearch, ZoneRebuild, ZoneLabel, ZoneBlocks, ZoneEquivalence, ZoneFlatten, PhaseCount };
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
 // GeneralsX @feature Codex 29/10/2026 Sample wall time at a fixed stride; never time every cell or extrapolate sampled totals.
 struct QueryProfile {
  static constexpr unsigned stride=128;
  std::uint64_t calls=0,samples=0,evaluationNanoseconds=0,loggingNanoseconds=0;
  std::array<std::uint64_t,4> stageCalls{},stageSamples{},stageEvaluation{},stageLogging{};
  template<class Evaluate,class Log>auto evaluate(Evaluate evaluateLive,Log log,unsigned stage=0){
   assert(stage<4);++stageCalls[stage];
   if(++calls%stride){auto result=evaluateLive();log(result);return result;}
   const auto start=Clock::now();
   auto result=evaluateLive();const auto evaluated=Clock::now();
   log(result);const auto logged=Clock::now();
   const auto evaluation=elapsed(start,evaluated),logging=elapsed(evaluated,logged);
   ++samples;evaluationNanoseconds+=evaluation;loggingNanoseconds+=logging;
   ++stageSamples[stage];stageEvaluation[stage]+=evaluation;stageLogging[stage]+=logging;
   return result;
  }
 private:
  static std::uint64_t elapsed(typename Clock::time_point start,typename Clock::time_point end){
   const auto ns=std::chrono::duration_cast<std::chrono::nanoseconds>(end-start).count();
   return ns>0?static_cast<std::uint64_t>(ns):0;
  }
 };
 struct ReadSample {
  std::uint64_t queries=0,queryObservations=0,heights=0,heightObservations=0;
  QueryProfile queryProfile;
  std::uint64_t hierarchyNanoseconds=0,fineNanoseconds=0,finalizationNanoseconds=0;
  unsigned flags=0;
 };
 // GeneralsX @feature Codex 28/10/2026 Bounded scalar summaries explain reached admission/policy failures without storing requests.
 struct AdmissionMismatch {
  std::uint64_t calls=0,higher=0,lower=0,equal=0;
  unsigned capturedMin=0,capturedMax=0,currentMin=0,currentMax=0;
 };
 enum ClosestField { Blocked, CostMultiplier, MoveAllies, GoalObstacle, StartedStuck, GotHierarchy, InitialIgnored, ClosestFieldCount };
 struct ClosestMismatch {
  std::uint64_t calls=0;
  std::array<std::uint64_t,ClosestFieldCount> fields{};
 };
 // GeneralsX @feature Codex 29/10/2026 Count only the first rejected cell/log per phase; snapshots contain no pointers or requests.
 enum CellField { Metadata, Obstacle, Fence, Transparent, Zone, AircraftGoal, Pinched, CellType, UnitFlags,
  ConnectsLayer, CellLayer, GoalUnit, GoalAircraft, PosUnit, InfoX, InfoY, EffectiveFence, EffectiveTransparent, EffectiveObstacle, CellFieldCount };
 struct CellRejections {
  std::uint64_t calls=0,values=0,logFull=0,captureFailed=0;
  unsigned entriesMin=0,entriesMax=0;
  std::array<std::uint64_t,CellFieldCount> fields{};
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
 // GeneralsX @feature Codex 29/10/2026 Retain bounded serial closest work, using the existing kernel timer and scalar counters only.
 struct ClosestSample {
  std::uint64_t nanoseconds=0,queue=0,pops=0,destinationChecks=0,candidates=0,improvements=0;
  std::uint64_t farTests=0,farPrunes=0,noHierarchy=0,over2000=0,nearGoal=0,expansions=0;
  unsigned examined=0,records=0,indexBytes=0,flags=0,outcome=0;
  int startX=0,startY=0,goalX=0,goalY=0,radius=0;
  float costMultiplier=0;
 };
 // GeneralsX @feature Codex 29/10/2026 Retain zone rebuilds separately so slow joined searches cannot evict their evidence.
 struct ZoneSample {
  std::uint64_t nanoseconds=0,queue=0;
  unsigned width=0,height=0,blocks=0,zones=0;
  std::array<std::uint64_t,4> stages{};
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
 // GeneralsX @feature Codex 29/10/2026 Private stage ownership restores nested classification on exceptions.
 class StageScope {
  BasicPathSearchTiming* m_owner;
  unsigned m_previous=0;
  Scope m_timer;
 public:
  StageScope(BasicPathSearchTiming* owner,Phase phase):m_owner(owner),m_timer(owner?&(*owner)[phase]:nullptr){
   if(owner){m_previous=owner->m_queryStage;owner->m_queryStage=phase==Hierarchy?1:phase==FineSearch?2:phase==Finalization?3:0;}
  }
  StageScope(const StageScope&)=delete;
  StageScope& operator=(const StageScope&)=delete;
  ~StageScope(){if(m_owner)m_owner->m_queryStage=m_previous;}
 };
 unsigned queryStage()const{return m_queryStage;}
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
 // GeneralsX @feature Codex 29/10/2026 Profile empty-queue rebuilds independently of request execution.
 class ZoneScope {
  BasicPathSearchTiming* m_owner;
  Scope m_timer;
  std::array<std::uint64_t,4> m_before{};
 public:
  ZoneSample sample;
  ZoneScope(BasicPathSearchTiming* owner,unsigned width,unsigned height):m_owner(owner),
   m_timer(owner?&(*owner)[ZoneRebuild]:nullptr){
   if(!owner)return;
   sample.width=width;sample.height=height;sample.queue=owner->m_activeQueue?owner->m_activeQueue->id:0;
   for(unsigned i=0;i<4;++i)m_before[i]=(*owner)[static_cast<Phase>(ZoneLabel+i)].totalNanoseconds;
  }
  ZoneScope(const ZoneScope&)=delete;
  ZoneScope& operator=(const ZoneScope&)=delete;
  Metric* metric(Phase phase){return m_owner?&(*m_owner)[phase]:nullptr;}
  ~ZoneScope(){
   if(!m_owner)return;
   sample.nanoseconds=m_timer.stop();
   for(unsigned i=0;i<4;++i)sample.stages[i]=(*m_owner)[static_cast<Phase>(ZoneLabel+i)].totalNanoseconds-m_before[i];
   retain(m_owner->m_slowZones,m_owner->m_slowZoneCount,sample);
  }
 };
 const std::array<ZoneSample,retainedSamples>& slowZones()const{return m_slowZones;}
 unsigned slowZoneCount()const{return m_slowZoneCount;}
 class SerialScope {
  Scope m_timer;
 public:
  SerialScope(BasicPathSearchTiming& owner,bool enabled,Kind kind):m_timer(enabled?&owner[SerialKernel]:nullptr){
   if(enabled){
    ++owner.m_serialKinds[static_cast<unsigned>(kind)];
    if(owner.m_activeQueue)++owner.m_activeQueue->serialKinds[static_cast<unsigned>(kind)];
   }
  }
  std::uint64_t stop(){return m_timer.stop();}
 };
 class ClosestScope {
  BasicPathSearchTiming& m_owner;
  SerialScope m_timer;
  bool m_enabled;
 public:
  ClosestSample sample;
  ClosestScope(BasicPathSearchTiming& owner,bool enabled):m_owner(owner),m_timer(owner,enabled,Kind::Closest),m_enabled(enabled){
   if(enabled)sample.queue=owner.m_activeQueue?owner.m_activeQueue->id:0;
  }
  ~ClosestScope(){if(m_enabled){sample.nanoseconds=m_timer.stop();retain(m_owner.m_slowClosest,m_owner.m_slowClosestCount,sample);}}
  ClosestScope(const ClosestScope&)=delete;
  ClosestScope& operator=(const ClosestScope&)=delete;
 };
 const std::array<ClosestSample,retainedSamples>& slowClosest()const{return m_slowClosest;}
 unsigned slowClosestCount()const{return m_slowClosestCount;}
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
 bool admissionMatches(bool fallback,unsigned captured,unsigned current){
  return admissionMatches(fallback,captured,current,captured==current);
 }
 // GeneralsX @feature Codex 29/10/2026 Separate rejected windows from count changes that actually survive all checks and finalization.
 bool admissionMatches(bool fallback,unsigned captured,unsigned current,bool sameDecisions){
  if(sameDecisions)return true;
  recordAdmission(m_admissionMismatch[unsigned(fallback)],captured,current);
  return false;
 }
 void admissionReused(bool fallback,unsigned captured,unsigned current){
  if(captured!=current)recordAdmission(m_admissionReuse[unsigned(fallback)],captured,current);
 }
 const AdmissionMismatch& admissionReuse(bool fallback)const{return m_admissionReuse[unsigned(fallback)];}
private:
 static void recordAdmission(AdmissionMismatch& s,unsigned captured,unsigned current){
  if(!s.calls){s.capturedMin=s.capturedMax=captured;s.currentMin=s.currentMax=current;}
  if(captured<s.capturedMin)s.capturedMin=captured;
  if(captured>s.capturedMax)s.capturedMax=captured;
  if(current<s.currentMin)s.currentMin=current;
  if(current>s.currentMax)s.currentMax=current;
  ++s.calls;if(current>captured)++s.higher;else if(current<captured)++s.lower;else ++s.equal;
 }
public:
 void cellLogRejected(bool fallback,unsigned entries,bool full){
  auto& s=beginCellRejection(fallback,entries);if(full)++s.logFull;else ++s.captureFailed;
 }
 void cellValuesRejected(bool fallback,unsigned entries,const std::array<unsigned,CellFieldCount>& before,
                         const std::array<unsigned,CellFieldCount>& current){
  auto& s=beginCellRejection(fallback,entries);++s.values;
  for(unsigned i=0;i<CellFieldCount;++i)if(before[i]!=current[i])++s.fields[i];
 }
 const CellRejections& cellRejections(bool fallback)const{return m_cellRejections[unsigned(fallback)];}
private:
 CellRejections& beginCellRejection(bool fallback,unsigned entries){
  auto& s=m_cellRejections[unsigned(fallback)];
  if(!s.calls)s.entriesMin=s.entriesMax=entries;
  if(entries<s.entriesMin)s.entriesMin=entries;
  if(entries>s.entriesMax)s.entriesMax=entries;
  ++s.calls;return s;
 }
public:
 template<class Settings> bool closestMatches(bool fallback,const Settings& captured,const Settings& current){
  if(captured==current)return true;
  auto& s=m_closestMismatch[unsigned(fallback)];++s.calls;
  const bool differences[]={captured.blocked!=current.blocked,captured.pathCostMultiplier!=current.pathCostMultiplier,
   captured.moveAllies!=current.moveAllies,captured.goalOnObstacle!=current.goalOnObstacle,
   captured.startedStuck!=current.startedStuck,captured.gotHierarchicalPath!=current.gotHierarchicalPath,
   captured.initialIgnored!=current.initialIgnored};
  static_assert(sizeof(differences)/sizeof(*differences)==ClosestFieldCount,"closest fields must match summary");
  for(unsigned i=0;i<ClosestFieldCount;++i)if(differences[i])++s.fields[i];
  return false;
 }
 const AdmissionMismatch& admissionMismatch(bool fallback)const{return m_admissionMismatch[unsigned(fallback)];}
 const ClosestMismatch& closestMismatch(bool fallback)const{return m_closestMismatch[unsigned(fallback)];}
 const std::array<QueueSample,retainedSamples>& slowQueues()const{return m_slowQueues;}
 const std::array<PairSample,retainedSamples>& slowPairs()const{return m_slowPairs;}
 unsigned slowQueueCount()const{return m_slowQueueCount;}
 unsigned slowPairCount()const{return m_slowPairCount;}
 std::uint64_t admissions(Admission reason)const{return m_admission[static_cast<unsigned>(reason)];}
 std::uint64_t predictions(unsigned slot,PathPredictionReason reason)const{return m_prediction[slot][static_cast<unsigned>(reason)];}
 Metric& operator[](Phase phase){return m_metrics[phase];}
 const Metric& operator[](Phase phase)const{return m_metrics[phase];}
 void report(FILE* output)const {
  const char* names[PhaseCount]={"queue","prepare","caller_prepare","pair","worker_kernel","caller_kernel","serial_kernel","validate","hierarchy","finalize",
   "fine_search","zone_rebuild","zone_label","zone_blocks","zone_equivalence","zone_flatten"};
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
   const auto& a=m_admissionMismatch[phase];
   std::fprintf(output,"[PATH_ADMISSION_MISMATCH] phase=%s calls=%llu higher=%llu lower=%llu captured_min=%u captured_max=%u current_min=%u current_max=%u equal=%llu\n",
    phase?"fallback":"primary",u(a.calls),u(a.higher),u(a.lower),a.capturedMin,a.capturedMax,a.currentMin,a.currentMax,u(a.equal));
   const auto& reuse=m_admissionReuse[phase];
   std::fprintf(output,"[PATH_ADMISSION_REUSE] phase=%s calls=%llu higher=%llu lower=%llu captured_min=%u captured_max=%u current_min=%u current_max=%u\n",
    phase?"fallback":"primary",u(reuse.calls),u(reuse.higher),u(reuse.lower),reuse.capturedMin,reuse.capturedMax,reuse.currentMin,reuse.currentMax);
   const auto& c=m_closestMismatch[phase];
   const char* closestFields[]={"blocked","cost_multiplier","move_allies","goal_obstacle","started_stuck","hierarchy","initial_ignored"};
   static_assert(sizeof(closestFields)/sizeof(*closestFields)==ClosestFieldCount,"closest names must match fields");
   std::fprintf(output,"[PATH_CLOSEST_MISMATCH] phase=%s calls=%llu",phase?"fallback":"primary",u(c.calls));
   for(unsigned i=0;i<ClosestFieldCount;++i)std::fprintf(output," %s=%llu",closestFields[i],u(c.fields[i]));
   std::fprintf(output,"\n");
   const auto& cells=m_cellRejections[phase];
   const char* cellFields[]={"metadata","obstacle","fence","transparent","zone","aircraft_goal","pinched","type","unit_flags",
    "connects_layer","layer","goal_unit","goal_aircraft","pos_unit","info_x","info_y","effective_fence","effective_transparent","effective_obstacle"};
   static_assert(sizeof(cellFields)/sizeof(*cellFields)==CellFieldCount,"cell names must match snapshot fields");
   std::fprintf(output,"[PATH_CELL_REJECTIONS] phase=%s calls=%llu values=%llu log_full=%llu capture_failed=%llu entries_min=%u entries_max=%u",
    phase?"fallback":"primary",u(cells.calls),u(cells.values),u(cells.logFull),u(cells.captureFailed),cells.entriesMin,cells.entriesMax);
   for(unsigned i=0;i<CellFieldCount;++i)std::fprintf(output," %s=%llu",cellFields[i],u(cells.fields[i]));
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
  for(unsigned i=0;i<m_slowClosestCount;++i){
   const auto&s=m_slowClosest[i];
   std::fprintf(output,"[PATH_CLOSEST_SLOW] rank=%u queue=%llu ms=%.3f start_x=%d start_y=%d goal_x=%d goal_y=%d radius=%d cost_multiplier=%.3f flags=%u outcome=%u pops=%llu destination_checks=%llu candidates=%llu improvements=%llu far_tests=%llu far_prunes=%llu no_hierarchy=%llu over_2000=%llu near_goal=%llu expansions=%llu examined=%u records=%u index_bytes=%u\n",
    i+1,u(s.queue),s.nanoseconds/1000000.0,s.startX,s.startY,s.goalX,s.goalY,s.radius,double(s.costMultiplier),s.flags,s.outcome,
    u(s.pops),u(s.destinationChecks),u(s.candidates),u(s.improvements),u(s.farTests),u(s.farPrunes),
    u(s.noHierarchy),u(s.over2000),u(s.nearGoal),u(s.expansions),s.examined,s.records,s.indexBytes);
  }
  for(unsigned i=0;i<m_slowZoneCount;++i){
   const auto&s=m_slowZones[i];
   std::fprintf(output,"[PATH_ZONE_SLOW] rank=%u queue=%llu ms=%.3f width=%u height=%u blocks=%u zones=%u label_ms=%.3f blocks_ms=%.3f equivalence_ms=%.3f flatten_ms=%.3f\n",
    i+1,u(s.queue),s.nanoseconds/1000000.0,s.width,s.height,s.blocks,s.zones,
    s.stages[0]/1000000.0,s.stages[1]/1000000.0,s.stages[2]/1000000.0,s.stages[3]/1000000.0);
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
  const auto&p=s.queryProfile;
  std::fprintf(output,"[PATH_TASK_PROFILE] pair=%llu role=%s phase=%s hierarchy_ms=%.3f fine_ms=%.3f finalize_ms=%.3f query_calls=%llu query_stride=%u query_samples=%llu sampled_evaluate_ms=%.6f sampled_log_ms=%.6f\n",
   u(pair),role,phase,s.hierarchyNanoseconds/1000000.0,s.fineNanoseconds/1000000.0,s.finalizationNanoseconds/1000000.0,
   u(p.calls),QueryProfile::stride,u(p.samples),p.evaluationNanoseconds/1000000.0,p.loggingNanoseconds/1000000.0);
  const char* stages[]={"prepare","hierarchy","fine","finalize"};
  for(unsigned i=0;i<4;++i)if(p.stageCalls[i])
   std::fprintf(output,"[PATH_QUERY_STAGE] pair=%llu role=%s phase=%s stage=%s calls=%llu samples=%llu sampled_evaluate_ms=%.6f sampled_log_ms=%.6f\n",
    u(pair),role,phase,stages[i],u(p.stageCalls[i]),u(p.stageSamples[i]),p.stageEvaluation[i]/1000000.0,p.stageLogging[i]/1000000.0);
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
 std::array<AdmissionMismatch,2> m_admissionMismatch{};
 std::array<AdmissionMismatch,2> m_admissionReuse{};
 std::array<ClosestMismatch,2> m_closestMismatch{};
 std::array<CellRejections,2> m_cellRejections{};
 std::array<QueueSample,retainedSamples> m_slowQueues{};
 std::array<PairSample,retainedSamples> m_slowPairs{};
 std::array<ClosestSample,retainedSamples> m_slowClosest{};
 std::array<ZoneSample,retainedSamples> m_slowZones{};
 unsigned m_slowZoneCount=0;
 unsigned m_slowQueueCount=0,m_slowPairCount=0,m_slowClosestCount=0;
 std::uint64_t m_queueId=0;
 QueueSample* m_activeQueue=nullptr;
 unsigned m_queryStage=0;
};
using PathSearchTiming=BasicPathSearchTiming<>;
