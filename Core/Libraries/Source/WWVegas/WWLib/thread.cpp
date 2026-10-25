/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2025 Electronic Arts Inc.
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/


#include "thread.h"
#include "Except.h"
#include "wwdebug.h"
#pragma warning ( push )
#pragma warning ( disable : 4201 )
#include "systimer.h"
#pragma warning ( pop )

#ifdef _WIN32
#include <process.h>
#include <windows.h>
#else
// GeneralsX @bugfix BenderAI 24/02/2026 Phase 5 - GetCurrentThreadIdAsInt for non-Windows
#include "thread_compat.h"
#endif
#ifdef _UNIX
#include <chrono>
#include <cstdio>
#include <exception>
#include <pthread.h>
#include <sched.h>
#endif

ThreadClass::ThreadClass(const char *thread_name, ExceptionHandlerType exception_handler) : handle(0), running(false), thread_priority(0)
{
	if (thread_name) {
		size_t nameLen = strlcpy(ThreadName, thread_name, ARRAY_SIZE(ThreadName));
		(void)nameLen; assert(nameLen < ARRAY_SIZE(ThreadName));
	} else {
		strcpy(ThreadName, "No name");
	}

	ExceptionHandler = exception_handler;
	ThreadID = 0;
}

ThreadClass::~ThreadClass()
{
	Stop();
}

void __cdecl ThreadClass::Internal_Thread_Function(void* params)
{
	ThreadClass* tc=reinterpret_cast<ThreadClass*>(params);
#ifndef _UNIX
	tc->running=true;
#endif
	// GeneralsX @bugfix BenderAI 24/02/2026 Phase 5 - pthread_t is a pointer on macOS; use int wrapper
#ifdef _WIN32
	tc->ThreadID = GetCurrentThreadId();
#else
	tc->ThreadID = GetCurrentThreadIdAsInt();
#endif

#ifdef _WIN32
	Register_Thread_ID(tc->ThreadID, tc->ThreadName);

#if defined(_MSC_VER)
	// MSVC supports structured exception handling (__try/__except)
	if (tc->ExceptionHandler != nullptr) {
		__try {
			tc->Thread_Function();
		} __except(tc->ExceptionHandler(GetExceptionCode(), GetExceptionInformation())) {};
	} else {
		tc->Thread_Function();
	}
#elif defined(__GNUC__) && defined(_WIN32)
	// GCC/MinGW-w64 doesn't support MSVC's __try/__except syntax
	// Call Thread_Function directly without SEH support
	tc->Thread_Function();
#else
	#error "ThreadClass::Internal_Thread_Function: Unsupported compiler. This code requires MSVC or GCC/MinGW-w64 targeting Windows."
#endif

#else //_WIN32
#ifdef _UNIX
	// GeneralsX @feature Codex 25/10/2026 A failed worker must report the failure and release its lifecycle state.
	try {
		tc->Thread_Function();
	} catch (const std::exception& error) {
		fprintf(stderr, "[THREAD_ERROR] %s: %s\n", tc->ThreadName, error.what());
	} catch (...) {
		fprintf(stderr, "[THREAD_ERROR] %s: unhandled worker exception\n", tc->ThreadName);
	}
#else
	tc->Thread_Function();
#endif
#endif //_WIN32

#ifdef _WIN32
	Unregister_Thread_ID(tc->ThreadID, tc->ThreadName);
#endif // _WIN32
	tc->ThreadID = 0;
#ifdef _UNIX
	{
		std::lock_guard<std::mutex> lock(tc->ExitMutex);
		tc->running = false;
		tc->handle = 0;
	}
	tc->ExitCondition.notify_all();
#else
	tc->handle=0;
#endif
}

void ThreadClass::Execute()
{
	#ifdef _UNIX
		// GeneralsX @feature Codex 25/10/2026 Publish the run flag before starting, so an immediate Stop cannot be lost.
		std::lock_guard<std::mutex> lock(LifecycleMutex);
		if (handle.load()) return;
		if (Worker.joinable()) Worker.join();
		running = true;
		handle = 1;
		try {
			Worker = std::thread(&Internal_Thread_Function, this);
		} catch (...) {
			running = false;
			handle = 0;
			throw;
		}
		Apply_Unix_Priority();
	#else
		WWASSERT(!handle);	// Only one thread at a time!
		handle=_beginthread(&Internal_Thread_Function,0,this);
		SetThreadPriority((HANDLE)handle,THREAD_PRIORITY_NORMAL+thread_priority);
		WWDEBUG_SAY(("ThreadClass::Execute: Started thread %s, thread ID is %X", ThreadName, handle));
	#endif
}

void ThreadClass::Set_Priority(int priority)
{
	#ifdef _UNIX
		std::lock_guard<std::mutex> lock(LifecycleMutex);
		thread_priority = priority;
		Apply_Unix_Priority();
	#else
		thread_priority=priority;
		if (handle) SetThreadPriority((HANDLE)handle,THREAD_PRIORITY_NORMAL+thread_priority);
	#endif
}

void ThreadClass::Stop(unsigned ms)
{
	#ifdef _UNIX
		// GeneralsX @feature Codex 25/10/2026 Join before freeing resources; forced cancellation could leave engine locks held.
		// A worker may request its own stop while its owner is already joining it.
		if (ThreadID.load() != 0 && ThreadID.load() == _Get_Current_Thread_ID()) {
			running = false;
			return;
		}
		std::lock_guard<std::mutex> lifecycleLock(LifecycleMutex);
		running = false;
		if (!Worker.joinable() || Worker.get_id() == std::this_thread::get_id()) return;
		{
			std::unique_lock<std::mutex> exitLock(ExitMutex);
			if (!ExitCondition.wait_for(exitLock, std::chrono::milliseconds(ms), [this] { return handle.load() == 0; })) {
				fprintf(stderr, "[THREAD_WAIT] %s: shutdown exceeded %u ms; waiting for safe completion\n", ThreadName, ms);
			}
		}
		Worker.join();
	#else
		running=false;
		unsigned time=TIMEGETTIME();
		while (handle) {
			if ((TIMEGETTIME()-time)>ms) {
				int res=TerminateThread((HANDLE)handle,0);
				res;	// just to silence compiler warnings
				WWASSERT(res);	// Thread still not killed!
				handle=0;
			}
			Sleep(0);
		}
	#endif
}

void ThreadClass::Sleep_Ms(unsigned ms)
{
#ifdef _UNIX
	std::this_thread::sleep_for(std::chrono::milliseconds(ms));
#else
	Sleep(ms);
#endif
}

#ifndef _UNIX
HANDLE test_event = ::CreateEvent (nullptr, FALSE, FALSE, "");
#endif

void ThreadClass::Switch_Thread()
{
	#ifdef _UNIX
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	#else
		//	::SwitchToThread ();
		::WaitForSingleObject (test_event, 1);
		//	Sleep(1);	// Note! Parameter can not be 0 (or the thread switch doesn't occur)
	#endif
}

// Return calling thread's unique thread id
unsigned ThreadClass::_Get_Current_Thread_ID()
{
	#ifdef _UNIX
		return static_cast<unsigned>(GetCurrentThreadIdAsInt());
	#else
		return GetCurrentThreadId();
	#endif
}

bool ThreadClass::Is_Running()
{
	return !!handle;
}

#ifdef _UNIX
// GeneralsX @feature Codex 25/10/2026 Apply only scheduler-supported priorities, without changing process-wide niceness.
void ThreadClass::Apply_Unix_Priority()
{
	if (!Worker.joinable() || !handle.load()) return;
	int policy = 0;
	sched_param parameters = {};
	if (pthread_getschedparam(Worker.native_handle(), &policy, &parameters) != 0) return;
	const int minimum = sched_get_priority_min(policy);
	const int maximum = sched_get_priority_max(policy);
	if (minimum < 0 || maximum <= minimum) return; // Normal Unix scheduling commonly has no adjustable priority range.
	const int normal = minimum + (maximum - minimum) / 2;
	int requested = normal;
	if (thread_priority < minimum - normal) requested = minimum;
	else if (thread_priority > maximum - normal) requested = maximum;
	else requested += thread_priority;
	parameters.sched_priority = requested;
	(void)pthread_setschedparam(Worker.native_handle(), policy, &parameters);
}
#endif
