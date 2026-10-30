#pragma once
#include "exclusivesearchworker.h"
#include <array>
#include <atomic>
#include <cstdint>

// GeneralsX @feature Codex 31/10/2026 Bounded dynamic claims with participant identity and an exception-safe joined lifetime.
// Reference: dement123, ZeroHourReimagined_1.0.0_source JobSystem; retain owner, FP and joined-failure contracts.
class JoinedSearchPool {
public:
 static constexpr unsigned maximumWorkers=2,maximumJobs=4,maximumParticipants=maximumWorkers+1;
 using EnvironmentError=ExclusiveSearchWorker::EnvironmentError;
 using Callback=std::function<void(unsigned,unsigned)>;
 using ThreadFactory=std::function<std::thread(std::function<void()>)>;
private:
 const std::thread::id m_owner=std::this_thread::get_id();
 const unsigned m_workers;
 std::array<std::thread,maximumWorkers> m_threads;
 std::mutex m_mutex;
 std::condition_variable m_wake,m_finished;
 std::uint64_t m_generation=0;
 bool m_stop=false,m_running=false;
 unsigned m_remaining=0,m_count=0;
 std::atomic<unsigned> m_next{0};
 std::atomic<bool> m_cancelled{false};
 std::fenv_t m_environment{};
 Callback m_callback;
 std::function<bool()> m_canRun;
 std::array<std::exception_ptr,maximumJobs> m_errors{};
 std::array<std::exception_ptr,maximumParticipants> m_participantErrors{};
 std::array<bool,maximumJobs> m_completed{};
 std::array<unsigned,maximumJobs> m_participant{};
 std::array<unsigned,maximumParticipants> m_counts{};
 static bool& active(){static thread_local bool value=false;return value;}
 struct ActiveScope {
  ActiveScope(){active()=true;}
  ~ActiveScope(){active()=false;}
 };
 static unsigned checkedWorkers(unsigned workers){
  if(workers>maximumWorkers)throw std::invalid_argument("Search worker count exceeds bounded capacity");
  return workers;
 }
 void work(unsigned participant)noexcept{
  ExclusiveSearchWorker::WorkerScope role(participant!=0);
  ActiveScope scope;
  try{
   for(;;){
    if(m_cancelled.load())return;
    // Restore before every callback, including successive jobs on the caller.
    if(std::fesetenv(&m_environment)!=0)throw EnvironmentError("Cannot restore pooled search floating-point environment");
    if(m_canRun&&!m_canRun()){m_cancelled.store(true);return;}
    const auto job=m_next.fetch_add(1);
    if(job>=m_count)return;
    m_participant[job]=participant;
    try{
     if(m_cancelled.load() || (m_canRun&&!m_canRun())){m_cancelled.store(true);continue;}
     m_callback(job,participant);m_completed[job]=true;++m_counts[participant];
    }catch(...){m_errors[job]=std::current_exception();}
   }
  }catch(...){m_participantErrors[participant]=std::current_exception();}
 }
 void loop(unsigned participant){
  std::uint64_t seen=0;
  for(;;){
   {
    std::unique_lock<std::mutex> lock(m_mutex);
    m_wake.wait(lock,[&]{return m_stop||m_generation!=seen;});
    if(m_stop)return;
    seen=m_generation;
   }
   work(participant);
   {
    std::lock_guard<std::mutex> lock(m_mutex);
    if(--m_remaining==0)m_finished.notify_one();
   }
  }
 }
 void shutdown()noexcept{
  {std::lock_guard<std::mutex> lock(m_mutex);m_stop=true;}
  m_wake.notify_all();
  for(auto&thread:m_threads)if(thread.joinable())thread.join();
 }
public:
 explicit JoinedSearchPool(unsigned workers,ThreadFactory factory={}):m_workers(checkedWorkers(workers)){
  try{
   for(unsigned i=0;i<m_workers;++i){
    std::function<void()> entry=[this,i]{loop(i+1);};
    m_threads[i]=factory?factory(std::move(entry)):std::thread(std::move(entry));
    if(!m_threads[i].joinable())throw std::logic_error("Search thread factory returned an empty thread");
   }
  }catch(...){shutdown();throw;}
 }
 ~JoinedSearchPool(){shutdown();}
 JoinedSearchPool(const JoinedSearchPool&)=delete;
 JoinedSearchPool&operator=(const JoinedSearchPool&)=delete;
 unsigned workers()const{return m_workers;}
 bool completed(unsigned job)const{if(job>=m_count)throw std::out_of_range("Search job index");return m_completed[job];}
 unsigned participant(unsigned job)const{if(job>=m_count)throw std::out_of_range("Search job index");return m_participant[job];}
 unsigned completedBy(unsigned participant)const{if(participant>m_workers)throw std::out_of_range("Search participant index");return m_counts[participant];}
 bool cancelled()const{return m_cancelled.load();}
 void stop(){
  if(std::this_thread::get_id()!=m_owner||active())throw std::logic_error("Search pool stop requires its idle owner");
  shutdown();
 }
 void run(unsigned count,Callback callback,std::function<bool()> canRun={}){
  if(std::this_thread::get_id()!=m_owner||active()||ExclusiveSearchWorker::onWorker())
   throw std::logic_error("Search pool dispatch requires its nonnested owner");
  if(count>maximumJobs)throw std::invalid_argument("Search job count exceeds bounded capacity");
  if(count&&!callback)throw std::invalid_argument("Search callback is empty");
  std::fenv_t environment;
  if(std::fegetenv(&environment)!=0)throw EnvironmentError("Cannot capture pooled search floating-point environment");
  std::unique_lock<std::mutex> lock(m_mutex);
  if(m_running||m_stop)throw std::logic_error("Search pool is not idle");
  m_running=true;m_count=count;m_next=0;m_cancelled=false;m_environment=environment;
  m_errors={};m_participantErrors={};m_completed={};m_counts={};m_participant.fill(maximumParticipants);
  m_callback=std::move(callback);m_canRun=std::move(canRun);
  m_remaining=m_workers;++m_generation;m_wake.notify_all();lock.unlock();
  work(0);
  lock.lock();m_finished.wait(lock,[&]{return m_remaining==0;});
  // No participant holds or can call the batch callback past this point.
  m_callback={};m_canRun={};m_running=false;
  const auto errors=m_errors;const auto participantErrors=m_participantErrors;lock.unlock();
  const auto restoreFailed=std::fesetenv(&environment)!=0;
  // Logical job order, then participant order: never choose an exception by arrival time.
  for(const auto&error:errors)if(error)std::rethrow_exception(error);
  for(const auto&error:participantErrors)if(error)std::rethrow_exception(error);
  if(restoreFailed)throw EnvironmentError("Cannot restore caller floating-point environment after pooled search");
 }
};
