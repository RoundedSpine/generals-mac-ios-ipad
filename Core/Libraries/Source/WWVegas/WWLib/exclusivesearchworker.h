#pragma once
#include <cfenv>
#include <condition_variable>
#include <exception>
#include <functional>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <utility>

// GeneralsX @feature Codex 27/10/2026 Synchronous exclusive search execution; owner waits without pumping engine callbacks.
class ExclusiveSearchWorker {
public:
 class EnvironmentError:public std::runtime_error {public:using std::runtime_error::runtime_error;};
private:
 std::mutex m_mutex;
 std::condition_variable m_wake,m_finished;
 std::function<void()> m_job;
 std::exception_ptr m_error;
 std::fenv_t m_environment{};
 bool m_pending=false,m_done=true,m_stop=false;
 const std::thread::id m_owner=std::this_thread::get_id();
 std::thread m_thread;
 static bool& workerFlag() {static thread_local bool flag=false;return flag;}
 void loop() {
  for(;;) {
   std::function<void()> job;
   std::fenv_t environment;
   {
    std::unique_lock<std::mutex> lock(m_mutex);
    m_wake.wait(lock,[&]{return m_stop||m_pending;});
    if(m_stop) return;
    job=std::move(m_job);environment=m_environment;m_pending=false;
   }
   std::exception_ptr error;
   workerFlag()=true;
   try {
    if(std::fesetenv(&environment)!=0) throw EnvironmentError("Cannot restore search floating-point environment");
    job();
   }catch(...){error=std::current_exception();}
   workerFlag()=false;
   job=nullptr;
   {std::lock_guard<std::mutex> lock(m_mutex);m_error=error;m_done=true;}
   m_finished.notify_one();
  }
 }
public:
 ExclusiveSearchWorker():m_thread([this]{loop();}){}
 ExclusiveSearchWorker(const ExclusiveSearchWorker&)=delete;
 ExclusiveSearchWorker&operator=(const ExclusiveSearchWorker&)=delete;
 ~ExclusiveSearchWorker(){
  {std::lock_guard<std::mutex> lock(m_mutex);m_stop=true;}
  m_wake.notify_one();
  m_thread.join();
 }
 static bool onWorker(){return workerFlag();}
 void run(std::function<void()> job){
  if(std::this_thread::get_id()!=m_owner) throw std::logic_error("Exclusive search dispatch requires its owner thread");
  std::fenv_t environment;
  if(std::fegetenv(&environment)!=0) throw EnvironmentError("Cannot capture search floating-point environment");
  std::unique_lock<std::mutex> lock(m_mutex);
  if(!m_done||m_stop) throw std::logic_error("Exclusive search worker is not idle");
  m_environment=environment;m_error=nullptr;m_job=std::move(job);m_done=false;m_pending=true;
  m_wake.notify_one();
  m_finished.wait(lock,[&]{return m_done;});
  auto error=m_error;lock.unlock();
  if(error) std::rethrow_exception(error);
 }
};
