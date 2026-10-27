#pragma once
#include <atomic>
#include <stdexcept>

// GeneralsX @refactor Codex 27/10/2026 Bind scratch explicitly and reject simultaneous ownership of one context.
struct SearchContextOwnership {
 std::atomic<void*> owner{nullptr};
 static void* threadIdentity() { static thread_local char identity;return &identity; }
};

template<class Context>
class SearchContextBinding {
 Context* m_previous;
 Context& m_context;
 bool m_acquired=false;
 static Context*& selected() { static thread_local Context* context=nullptr;return context; }
public:
 explicit SearchContextBinding(Context& context):m_previous(selected()),m_context(context) {
  void* expected=nullptr;
  m_acquired=context.m_ownership.owner.compare_exchange_strong(expected,SearchContextOwnership::threadIdentity());
  if(!m_acquired && expected!=SearchContextOwnership::threadIdentity())
   throw std::logic_error("Search context already owned by another thread");
  selected()=&context;
 }
 ~SearchContextBinding() {
  selected()=m_previous;
  if(m_acquired) m_context.m_ownership.owner.store(nullptr);
 }
 SearchContextBinding(const SearchContextBinding&)=delete;
 SearchContextBinding& operator=(const SearchContextBinding&)=delete;
 bool canTransfer() const { return m_acquired && !m_previous && selected()==&m_context; }
 template<class Function>
 void transferAndWait(Function function) {
  if(!canTransfer()) throw std::logic_error("Only a top-level search binding can transfer ownership");
  selected()=m_previous;m_context.m_ownership.owner.store(nullptr);m_acquired=false;
  auto restore=[&]{
   void* expected=nullptr;
   if(!m_context.m_ownership.owner.compare_exchange_strong(expected,SearchContextOwnership::threadIdentity()))
    throw std::logic_error("Search handoff returned before context ownership was released");
   m_acquired=true;selected()=&m_context;
  };
  try {function();}catch(...){restore();throw;}
  restore();
 }
 static Context* current() { return selected(); }
};
