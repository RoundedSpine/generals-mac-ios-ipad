#pragma once
#include "pathoccupancyquery.h"
#include <atomic>
#include <condition_variable>
#include <cstdint>
#include <cstdio>
#include <mutex>
#include <thread>

// GeneralsX @feature Codex 27/10/2026 One bounded shadow validator; never search/apply against the live world.
namespace PathOccupancy {
inline std::atomic<bool>& validationPaused() { static std::atomic<bool> paused{false};return paused; }
inline std::atomic<std::uint64_t>& validationLifecycleEpoch() { static std::atomic<std::uint64_t> epoch{0};return epoch; }
inline void setValidationPaused(bool value) {
 if(validationPaused().exchange(value)!=value) ++validationLifecycleEpoch();
}
class ValidationWorker {
 std::mutex m_mutex;
 std::condition_variable m_condition;
 Transcript m_pending{};
 bool m_hasPending=false,m_stopping=false;
 std::uint64_t m_epoch=0,m_pendingEpoch=0,m_pendingLifecycle=0;
 std::atomic<std::uint64_t> m_validated{0},m_mismatches{0},m_skipped{0};
 std::thread m_thread;
 void loop() {
  for(;;) {
   Transcript local;
   std::uint64_t epoch,lifecycle;
   {
    std::unique_lock<std::mutex> lock(m_mutex);
    m_condition.wait(lock,[&]{return m_stopping||m_hasPending;});
    if(m_stopping) return;
    local=m_pending;epoch=m_pendingEpoch;lifecycle=m_pendingLifecycle;m_hasPending=false;
   }
   bool matched=false;
   try { matched=validate(local); } catch(const std::exception&) { matched=false; }
   {
    std::lock_guard<std::mutex> lock(m_mutex);
    // Historical results from paused/reset sessions are discarded, never applied.
    if(m_stopping || epoch!=m_epoch || lifecycle!=validationLifecycleEpoch().load() || validationPaused().load()) {++m_skipped;continue;}
    if(matched) ++m_validated;
    else if(m_mismatches.fetch_add(1)==0) std::fprintf(stderr,"[PATH_OCCUPANCY_WORKER] mismatch in copied-query replay; gameplay remains serial\n");
   }
  }
 }
public:
 ValidationWorker():m_thread([this]{loop();}) {}
 ValidationWorker(const ValidationWorker&)=delete;
 ValidationWorker& operator=(const ValidationWorker&)=delete;
 ~ValidationWorker() {stop();}
 void stop() {
  {std::lock_guard<std::mutex> lock(m_mutex);m_stopping=true;m_hasPending=false;}
  m_condition.notify_one();
  if(m_thread.joinable()) m_thread.join();
 }
 bool submit(const Transcript& transcript) {
  if(transcript.overflow || validationPaused().load()) {++m_skipped;return false;}
  // Main thread never waits for worker computation or for a queue slot.
  std::unique_lock<std::mutex> lock(m_mutex,std::try_to_lock);
  if(!lock.owns_lock() || m_stopping || m_hasPending) {++m_skipped;return false;}
  m_pending=transcript;m_pendingEpoch=m_epoch;m_pendingLifecycle=validationLifecycleEpoch().load();m_hasPending=true;
  lock.unlock();m_condition.notify_one();return true;
 }
 void invalidate() {
  std::lock_guard<std::mutex> lock(m_mutex);++m_epoch;m_hasPending=false;
 }
 std::uint64_t validated() const {return m_validated.load();}
 std::uint64_t mismatches() const {return m_mismatches.load();}
 std::uint64_t skipped() const {return m_skipped.load();}
};
}
