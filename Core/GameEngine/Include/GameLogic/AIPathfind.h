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

////////////////////////////////////////////////////////////////////////////////
//																																						//
//  (c) 2001-2003 Electronic Arts Inc.																				//
//																																						//
////////////////////////////////////////////////////////////////////////////////

// AIPathfind.h
// AI pathfinding system
// Author: Michael S. Booth, October 2001

#pragma once

#include "Common/GameType.h"
#include "Common/GameMemory.h"
#include "Common/Snapshot.h"

#include <vector>
#include <array>
#include "stampedsearchcontext.h"
#include "boundedkeyedpool.h"
#include "boundedrecordindex.h"
#include "searchcontextbinding.h"
#include "searchadmissionwindow.h"

#if defined(GENERALS_SEARCH_CONTEXT) && RTS_ZEROHOUR
#define GENERALS_ZH_SEARCH_CONTEXT 1
#endif
// GeneralsX @performance Codex 30/10/2026 Experimental rebuild merges preserve minimum labels and publish ordinary flat tables.
#if defined(GENERALS_FAST_ZONE_MERGES) && RTS_ZEROHOUR
#define GENERALS_ZH_FAST_ZONE_MERGES 1
#include "minimumzoneequivalence.h"
#endif
#if defined(GENERALS_OCCUPANCY_WORKER) && defined(GENERALS_ZH_SEARCH_CONTEXT)
#define GENERALS_ZH_OCCUPANCY_WORKER 1
namespace PathOccupancy { struct Input; struct Result; }
struct PathfindOccupancyValidation;
#endif
#if defined(GENERALS_EXCLUSIVE_PATH_WORKER) && defined(GENERALS_ZH_SEARCH_CONTEXT)
#define GENERALS_ZH_EXCLUSIVE_PATH_WORKER 1
struct PathfindExclusiveWorker;
#endif
// GeneralsX @feature Codex 27/10/2026 Frozen two-request batches require the real worker and explicit occupancy decisions.
#if defined(GENERALS_PARALLEL_PATH_BATCH) && defined(GENERALS_ZH_EXCLUSIVE_PATH_WORKER) && defined(GENERALS_ZH_OCCUPANCY_WORKER)
#define GENERALS_ZH_PARALLEL_PATH_BATCH 1
struct PathfindParallelBatch;
struct PathfindParallelJob;
struct PathfindParallelReads;
void observeParallelCorridor(std::size_t block, Bool passable);
#endif
// GeneralsX @feature Codex 29/10/2026 Whole requests use the same joined two-participant dispatcher and bounded allocation policy.
#if defined(GENERALS_COMPLETE_PATH_WORKER) && defined(GENERALS_ZH_PARALLEL_PATH_BATCH)
#define GENERALS_ZH_COMPLETE_PATH_WORKER 1
#endif
// GeneralsX @performance Codex 30/10/2026 Bounded partner lookahead requires completed independently validated results.
#if defined(GENERALS_PATH_LOOKAHEAD) && defined(GENERALS_ZH_COMPLETE_PATH_WORKER)
#define GENERALS_ZH_PATH_LOOKAHEAD 1
#include "pathlookaheadwindow.h"
#endif
// GeneralsX @performance Codex 30/10/2026 Completed results no longer retain their participant's search arena.
#if defined(GENERALS_REUSE_PATH_CONTEXTS) && defined(GENERALS_ZH_COMPLETE_PATH_WORKER)
#define GENERALS_ZH_REUSE_PATH_CONTEXTS 1
#endif
// GeneralsX @feature Codex 31/10/2026 Participant-owned arenas require complete results and the independent publication snapshot.
#if defined(GENERALS_PATH_WORKER_POOL) && defined(GENERALS_ZH_REUSE_PATH_CONTEXTS)
#define GENERALS_ZH_PATH_WORKER_POOL 1
#endif
// GeneralsX @performance Codex 30/10/2026 Memoization is restricted to the already joined, frozen complete request lifetime.
#if defined(GENERALS_FROZEN_OCCUPANCY_CACHE) && defined(GENERALS_ZH_COMPLETE_PATH_WORKER)
#define GENERALS_ZH_FROZEN_OCCUPANCY_CACHE 1
#endif
// GeneralsX @feature Codex 28/10/2026 Timing storage exists only in the optional experimental profiler.
#if defined(GENERALS_PATH_TIMING) && defined(GENERALS_ZH_PARALLEL_PATH_BATCH)
#define GENERALS_ZH_PATH_TIMING 1
#include "pathsearchtiming.h"
#endif
//#include "GameLogic/Locomotor.h"	// no, do not include this, unless you like long recompiles
#include "GameLogic/LocomotorSet.h"
#include "GameLogic/GameLogic.h"

class Bridge;
class Object;
class Weapon;
class PathfindZoneManager;
class PathfindCell;

// How close is close enough when moving.

#define PATHFIND_CLOSE_ENOUGH 1.0f
#define PATH_MAX_PRIORITY 0x7FFFFFFF

#define INFANTRY_MOVES_THROUGH_INFANTRY

#if !RETAIL_COMPATIBLE_PATHFINDING
#undef RETAIL_COMPATIBLE_PATHFINDING_ALLOCATION
#endif

  typedef UnsignedShort zoneStorageType;


//----------------------------------------------------------------------------------------------------------

/**
 * PathNodes are used to create a final Path to return from the
 * pathfinder.  Note that these are not used during the A* search.
 */
class PathNode : public MemoryPoolObject
{
public:
	PathNode();

#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
	// GeneralsX @bugfix Codex 29/10/2026 Warm the private lazy pool on main without exposing allocator access.
	static void prepareMemoryPoolForSearch() { getClassMemoryPool(); }
#endif

	Coord3D *getPosition() { return &m_pos; }			///< return position of this node
	const Coord3D *getPosition() const { return &m_pos; }			///< return position of this node
	void setPosition( const Coord3D *pos ) { m_pos = *pos; }	///< set the position of this path node

	const Coord3D *computeDirectionVector();			///< compute direction to next node

	PathNode *getNext() { return m_next; }				///< return next node in the path
	PathNode *getPrevious() { return m_prev; }		///< return previous node in the path
	const PathNode *getNext() const { return m_next; }				///< return next node in the path
	const PathNode *getPrevious() const { return m_prev; }		///< return previous node in the path

	PathfindLayerEnum getLayer() const { return m_layer; }				///< return layer of this node.
	void setLayer( PathfindLayerEnum layer ) { m_layer = layer; }	///< set the layer of this path node

	void setNextOptimized( PathNode *node );

	PathNode *getNextOptimized(Coord2D* dir = nullptr, Real* dist = nullptr)  	///< return next node in optimized path
	{
		if (dir)
			*dir = m_nextOptiDirNorm2D;
		if (dist)
			*dist = m_nextOptiDist2D;
		return m_nextOpti;
	}

	const PathNode *getNextOptimized(Coord2D* dir = nullptr, Real* dist = nullptr) const  	///< return next node in optimized path
	{
		if (dir)
			*dir = m_nextOptiDirNorm2D;
		if (dist)
			*dist = m_nextOptiDist2D;
		return m_nextOpti;
	}

	void setCanOptimize(Bool canOpt) { m_canOptimize = canOpt;}
	Bool getCanOptimize() const { return m_canOptimize;}

	/// given a list, prepend this node, return new list
	PathNode *prependToList( PathNode *list );

	/// given a list, append this node, return new list.  slow implementation.
	/// @todo optimize this
	PathNode *appendToList( PathNode *list );

	/// given a node, append to this node
	void append( PathNode *list );

public:
	mutable Int					m_id; // Used in Path::xfer() to save & recreate the path list.

private:
	MEMORY_POOL_GLUE_WITH_USERLOOKUP_CREATE( PathNode, "PathNodePool"  );		///< @todo Set real numbers for mem alloc

	PathNode*						m_nextOpti;													///< next node in the optimized path
	PathNode*						m_next;															///< next node in the path
	PathNode*						m_prev;															///< previous node in the path
	Coord3D							m_pos;															///< position of node in space
	PathfindLayerEnum		m_layer;														///< Layer for this section.
	Bool								m_canOptimize;											///< True if this cell can be optimized out.

	Real								m_nextOptiDist2D;										///< if nextOpti is nonnull, the dist to it.
	Coord2D							m_nextOptiDirNorm2D;								///< if nextOpti is nonnull, normalized dir vec towards it.

};

// this doesn't actually seem to be a particularly useful win,
// performance-wise, so I didn't enable it. (srj)
#define NO_CPOP_STARTS_FROM_PREV_SEG

struct ClosestPointOnPathInfo
{
	Real								distAlongPath;
	Coord3D							posOnPath;
	PathfindLayerEnum		layer;
};

/**
 * This class encapsulates a "path" returned by the Pathfinder.
 */
class Path : public MemoryPoolObject, public Snapshot
{
public:
	Path();

#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
	// GeneralsX @bugfix Codex 29/10/2026 Warm the private lazy pool on main without exposing allocator access.
	static void prepareMemoryPoolForSearch() { getClassMemoryPool(); }
#endif

	PathNode *getFirstNode() { return m_path; }
	PathNode *getLastNode() { return m_pathTail; }

	void updateLastNode( const Coord3D *pos );

	void prependNode( const Coord3D *pos, PathfindLayerEnum layer );				///< Create a new node at the head of the path
	void appendNode( const Coord3D *pos, PathfindLayerEnum layer );				///< Create a new node at the end of the path
	void setBlockedByAlly(Bool blocked) {m_blockedByAlly = blocked;}
	Bool getBlockedByAlly() {return m_blockedByAlly;}
	void optimize( const Object *obj, LocomotorSurfaceTypeMask acceptableSurfaces, Bool blocked );			///< Optimize the path to discard redundant nodes

	void optimizeGroundPath( Bool crusher, Int diameter );			///< Optimize the ground path to discard redundant nodes

	/// Given a location, return nearest location on path, and along-path dist to end as function result
	void computePointOnPath( const Object *obj, const LocomotorSet& locomotorSet, const Coord3D& pos, ClosestPointOnPathInfo& out);

	/// Given a location, return nearest location on path, and along-path dist to end as function result
	void peekCachedPointOnPath( Coord3D& pos ) const {pos = m_cpopOut.posOnPath;}

	/// Given a flight path, compute the distance to goal (0 if we are past it) & return the goal pos.
	Real computeFlightDistToGoal( const Coord3D *pos, Coord3D& goalPos );

	/// Given a location, return closest location on path, and along-path dist to end as function result
	void markOptimized() {m_isOptimized = true;}

protected:
	// snapshot interface
	virtual void crc( Xfer *xfer ) override;
	virtual void xfer( Xfer *xfer ) override;
	virtual void loadPostProcess() override;

protected:
	enum {MAX_CPOP=20};			///< Max times we will return the cached cpop.
	MEMORY_POOL_GLUE_WITH_USERLOOKUP_CREATE( Path, "PathPool" );							///< @todo Set real numbers for mem alloc

	PathNode*		m_path;															///< The list of PathNode objects that define the path
	PathNode*		m_pathTail;
	Bool				m_isOptimized;											///< True if the path has been optimized
	Bool				m_blockedByAlly;										///< An ally needs to move off of this path.
	// caching info for computePointOnPath.
	Bool										m_cpopValid;
	Int											m_cpopCountdown;				///< We only return the same cpop MAX_CPOP times.  It is occasionally possible to get stuck.
	Coord3D									m_cpopIn;
	ClosestPointOnPathInfo	m_cpopOut;
	const PathNode*					m_cpopRecentStart;
};

//----------------------------------------------------------------------------------------------------------

// See GameType.h for
// enum {LAYER_INVALID = 0, LAYER_GROUND = 1, LAYER_TOP=2 };

// Fits in 4 bits for now
enum {MAX_WALL_PIECES = 128};

// GeneralsX @feature Codex 26/10/2026 Search-only state is isolated from permanent unit/obstacle records.
class PathfindCellInfo;
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 struct PathfindSearchNode;
 using PathfindSearchRecord=PathfindSearchNode;
#else
 using PathfindSearchRecord=PathfindCellInfo;
#endif
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 // GeneralsX @performance Codex 29/10/2026 Map identities are shared read-only; record-slot indexes belong to each context.
 inline SearchCellIndices& pathfindSearchCellIndices(){static SearchCellIndices indices;return indices;}
 inline unsigned pathfindCellSearchIndex(const PathfindCell* cell);
#endif
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
 // GeneralsX @bugfix Codex 29/10/2026 Allocation through cached cell pointers must retain the permanent/persistent dependency too.
 void observeParallelAllocationCell(PathfindParallelReads* reads,PathfindCell* cell);
#endif
struct PathfindSearchState {
 PathfindSearchRecord *m_nextOpen = nullptr, *m_prevOpen = nullptr, *m_pathParent = nullptr;
 unsigned long long m_openSequence = 0;
 Int m_openIndex = -1;
 UnsignedShort m_totalCost = 0, m_costSoFar = 0;
 Bool m_open = false, m_closed = false, m_blockedByAlly = false;
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 Bool m_searchCharged=false;
#endif
};
#ifdef GENERALS_ZH_SEARCH_CONTEXT
// GeneralsX @performance Codex 29/10/2026 Private nodes contain search state, cell/position and allocation credit, without permanent occupancy fields.
struct PathfindSearchNode : PathfindSearchState {
 PathfindCell* m_cell=nullptr;
 ICoord2D m_pos{};
 PathfindSearchState& search()const{return *const_cast<PathfindSearchNode*>(this);}
};
#endif
constexpr unsigned PATHFIND_RECORD_CAPACITY = 30000;
using PathfindSearchNodes = StampedSearchContext<PathfindSearchState, PATHFIND_RECORD_CAPACITY>;
// Legacy arena access; compact contexts own complete nodes directly.
#ifndef GENERALS_ZH_SEARCH_CONTEXT
inline PathfindSearchNodes& mainPathfindSearchNodes();
#endif

class PathfindCellInfo
{
	friend class PathfindCell;
	friend class PathfindCellList;
 friend struct PathfindSearchContext;
public:
#if RETAIL_COMPATIBLE_PATHFINDING
	static void forceCleanPathFindCellInfos();
#endif
	static void allocateCellInfos();
	static void releaseCellInfos();

	static PathfindCellInfo * getACellInfo(PathfindCell *cell, const ICoord2D &pos);
	static void releaseACellInfo(PathfindCellInfo *theInfo);

	// GeneralsX @performance Codex 29/10/2026 Permanent records have no search-state pointer in the independent-context build.
#ifndef GENERALS_ZH_SEARCH_CONTEXT
	PathfindSearchState& search() const {
		return const_cast<PathfindCellInfo*>(this)->m_search;
	}
#endif
	PathfindCellInfo*& freeLink() {
#ifdef GENERALS_ZH_SEARCH_CONTEXT
		return m_nextFree;
#else
		return m_search.m_pathParent; // Retain legacy free-list aliasing when the experiment is disabled.
#endif
	}

protected:
 static unsigned s_recordsInUse; // Permanent pool use; independent searches never mutate this counter.
	static PathfindCellInfo *s_infoArray;
	static PathfindCellInfo *s_firstFree;							///<


	PathfindCell *m_cell;
#ifdef GENERALS_ZH_SEARCH_CONTEXT
	PathfindCellInfo* m_nextFree;
#else
	PathfindSearchState m_search;
#endif

	/// have to include cell's coordinates, since cells are often accessed via pointer only
	ICoord2D m_pos;

	ObjectID m_goalUnitID; ///< The objectID of the ground unit whose goal this is.
	ObjectID m_posUnitID;  ///< The objectID of the ground unit that is occupying this cell.
	ObjectID m_goalAircraftID; ///< The objectID of the aircraft whose goal this is.

	ObjectID m_obstacleID;	///< the object ID who overlaps this cell

	UnsignedInt m_isFree:1;
	UnsignedInt m_obstacleIsFence:1;///< True if occupied by a fence.
	UnsignedInt m_obstacleIsTransparent:1;///< True if obstacle is transparent (undefined if obstacleid is invalid)
	/// @todo Do we need both mark values in this cell?  Can't store a single value and compare it?
};

// TheSuperHackers @info The PathfindCellList class acts as a new management class for the pathfindcell open and closed lists
class PathfindCellList
{
	friend class PathfindCell;

public:
	// GeneralsX @performance Codex 26/10/2026 Use the heap only for the open list; keep closed-list links unchanged.
	explicit PathfindCellList(Bool useHeap = false) : m_head(nullptr), m_tail(nullptr),
		m_heapEnabled(useHeap), m_heapActive(useHeap), m_sequence(0) {}

#if RETAIL_COMPATIBLE_PATHFINDING
	void reset(PathfindCell* newHead = nullptr);
#else
	void reset();
#endif

	PathfindCell* getHead() const { return m_heapActive ? (m_heap.empty() ? nullptr : m_heap[0]->m_cell) : m_head; }
	Bool empty() const { return getHead() == nullptr; }
 // GeneralsX @refactor Codex 26/10/2026 Release global context buffers before game memory shuts down.
 void releaseStorage() { reset(); std::vector<PathfindSearchRecord*>().swap(m_heap); }
	PathfindCell* getNextForDisplay(PathfindCell* cell) const;

	Bool canReverseSort(PathfindCell& currentCell) const;

private:
	PathfindCell* m_head;
	PathfindCell* m_tail;
	Bool m_heapEnabled;
	Bool m_heapActive;
	unsigned long long m_sequence;
	std::vector<PathfindSearchRecord*> m_heap;

	static Bool before(const PathfindSearchRecord* a, const PathfindSearchRecord* b);
	void pushHeap(PathfindSearchRecord* info);
	void removeHeap(PathfindSearchRecord* info);
	void siftUp(Int index);
	void siftDown(Int index);
	void useLinkedList();
};

// GeneralsX @refactor Codex 26/10/2026 Own serial search lists, control flags and corridor scratch together.
struct PathfindSearchBookkeeping {
 PathfindCellList m_openList{true};
 PathfindCellList m_closedList;
 Bool m_isTunneling = false;
 ObjectID m_ignoreObstacleID = INVALID_ID;
 Int m_cumulativeCellsAllocated = 0;
};

struct PathfindSearchContext :
#ifndef GENERALS_ZH_SEARCH_CONTEXT
 PathfindSearchNodes,
#endif
 PathfindSearchBookkeeping {
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 // GeneralsX @refactor Codex 26/10/2026 Searches own records and never attach them to permanent map cells.
 BoundedKeyedPool<const PathfindCell*, PathfindSearchRecord, PATHFIND_RECORD_CAPACITY> m_records;
 BoundedRecordIndex<PATHFIND_RECORD_CAPACITY> m_recordIndex;
 unsigned m_transientRecords = 0;
 SearchContextOwnership m_ownership;
 // GeneralsX @bugfix Codex 29/10/2026 Speculative preparation and complete participants must never perform live-world retail recovery.
 struct SpeculativeRecovery {};
 bool m_speculativePreparation=false;
 void abortSpeculativeRecovery() const {if(m_speculativePreparation)throw SpeculativeRecovery{};}
 struct PreparationScope {
  PathfindSearchContext& context;bool previous;
  explicit PreparationScope(PathfindSearchContext& selected):context(selected),previous(selected.m_speculativePreparation){
   assert(SearchContextBinding<PathfindSearchContext>::current()==&context);context.m_speculativePreparation=true;
  }
  ~PreparationScope(){context.m_speculativePreparation=previous;}
  PreparationScope(const PreparationScope&)=delete;
  PreparationScope& operator=(const PreparationScope&)=delete;
 };
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
 PathfindParallelReads* m_parallelReads = nullptr;
 SearchAdmissionWindow<PATHFIND_RECORD_CAPACITY> m_admissionWindow;
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
 // GeneralsX @feature Codex 29/10/2026 Accumulate admission across hierarchy/fine generations without changing either phase's predicate.
 SearchAdmissionWindow<PATHFIND_RECORD_CAPACITY>* m_requestAdmission=nullptr;
 PathfindParallelJob* m_completeJob=nullptr;
 bool m_completeExecuting=false,m_completeBegan=false,m_completeCorridorWritten=false;
#ifdef GENERALS_ZH_PATH_TIMING
 // Each executing complete request owns its phase metrics; the caller merges after joining.
 PathSearchTiming* m_privateTiming=nullptr;
#endif
#endif
 // GeneralsX @performance Codex 29/10/2026 Query-only cell reads are validated by their complete returned occupancy result.
 bool m_occupancyQueryReads=false;
 struct OccupancyReadScope {
  PathfindSearchContext& context;bool previous;
  explicit OccupancyReadScope(PathfindSearchContext& selected):context(selected),previous(selected.m_occupancyQueryReads){
   context.m_occupancyQueryReads=true;
  }
  ~OccupancyReadScope(){context.m_occupancyQueryReads=previous;}
  OccupancyReadScope(const OccupancyReadScope&)=delete;
  OccupancyReadScope& operator=(const OccupancyReadScope&)=delete;
 };
#endif
 // GeneralsX @refactor Codex 27/10/2026 Admission reads an explicit frozen count while an ordinary phase is bound.
 bool m_hasAdmissionSnapshot = false;
 unsigned m_permanentAdmission = 0;
 static unsigned permanentRecordsInUse() { return PathfindCellInfo::s_recordsInUse; }
 unsigned admissionUse()const{return m_hasAdmissionSnapshot?m_permanentAdmission:permanentRecordsInUse();}
 struct AdmissionScope {
  PathfindSearchContext& context;
  bool previousCaptured;
  unsigned previousAdmission;
  AdmissionScope(PathfindSearchContext& selected, unsigned permanentUse):context(selected),
   previousCaptured(selected.m_hasAdmissionSnapshot),previousAdmission(selected.m_permanentAdmission) {
   if (SearchContextBinding<PathfindSearchContext>::current()!=&context)
    throw std::logic_error("Admission capture requires a bound search context");
   if (permanentUse>PATHFIND_RECORD_CAPACITY)
    throw std::invalid_argument("Permanent search admission exceeds record capacity");
   context.m_hasAdmissionSnapshot=true;context.m_permanentAdmission=permanentUse;
  }
  ~AdmissionScope() {
   context.m_hasAdmissionSnapshot=previousCaptured;context.m_permanentAdmission=previousAdmission;
  }
  AdmissionScope(const AdmissionScope&)=delete;
  AdmissionScope& operator=(const AdmissionScope&)=delete;
 };

 // GeneralsX @performance Codex 29/10/2026 Registered cells use one indexed slot read; unregistered/over-budget identities keep the original allocator lookup.
 PathfindSearchRecord* findRecord(const PathfindCell* cell) {
  const unsigned index=pathfindCellSearchIndex(cell);
  if(!m_recordIndex.covers(index))return m_records.find(cell);
  const unsigned slot=m_recordIndex.find(index);
  return slot==m_recordIndex.missing?nullptr:m_records.atSlot(slot);
 }
 PathfindSearchRecord* allocateRecord(PathfindCell* cell, const ICoord2D& pos, Bool persistent) {
  if (auto* record = findRecord(cell)) return record;
  // Occupied cells already consume permanent capacity; only other search cells consume extra credit.
  const unsigned permanentUse = admissionUse();
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
  // GeneralsX @performance Codex 29/10/2026 Only speculative phases record an interval; serial/finalizer admission retains its original predicate.
  if(m_parallelReads){
   observeParallelAllocationCell(m_parallelReads,cell);
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
   if(!persistent && m_requestAdmission)m_requestAdmission->allows(permanentUse,m_transientRecords);
#endif
   if(!persistent && !m_admissionWindow.allows(permanentUse,m_transientRecords))return nullptr;
  }else
#endif
  if (!persistent && permanentUse + m_transientRecords >= PATHFIND_RECORD_CAPACITY) return nullptr;
  auto* record = m_records.acquire(cell);
  if (!record) return nullptr;
  record->m_cell = cell; record->m_pos = pos;
  // GeneralsX @performance Codex 29/10/2026 acquire already initialized the complete node once; publish only after cell/credit setup.
  record->m_searchCharged = !persistent;
  if (record->m_searchCharged) ++m_transientRecords;
  const unsigned index=pathfindCellSearchIndex(cell);
  if(m_recordIndex.covers(index))m_recordIndex.publish(index,m_records.index(record));
  return record;
 }
 void releaseRecord(const PathfindCell* cell) {
  auto* record = findRecord(cell);
  if (!record) return;
  if (record->m_searchCharged) { assert(m_transientRecords); --m_transientRecords; }
  record->search() = PathfindSearchState{};
  m_recordIndex.erase(pathfindCellSearchIndex(cell));
  m_records.release(cell);
 }
 auto generation()const{return m_records.generation();}
#endif
 void beginSearch(bool prepareIndex=true) {
#ifdef GENERALS_ZH_SEARCH_CONTEXT
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
  if(m_completeExecuting)m_completeBegan=true;
#endif
  m_records.beginGeneration(); m_transientRecords = 0;
  m_recordIndex.beginSearch(prepareIndex?pathfindSearchCellIndices().size():0);
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
  m_admissionWindow.reset();
#endif
#else
  PathfindSearchNodes::beginSearch();
#endif
 }
 // One byte per hierarchical block, not per terrain cell. A new map starts fully passable.
 std::vector<unsigned char> m_corridor;
 void resizeCorridor(std::size_t blocks) {
  if (!blocks) std::vector<unsigned char>().swap(m_corridor);
  else m_corridor.assign(blocks, 1);
 }
 void releaseStorage() {
  beginSearch(false);
  m_openList.releaseStorage();
  m_closedList.releaseStorage();
  resizeCorridor(0);
#ifdef GENERALS_ZH_SEARCH_CONTEXT
  m_recordIndex.releaseStorage();
#endif
  m_isTunneling = false;
  m_ignoreObstacleID = INVALID_ID;
  m_cumulativeCellsAllocated = 0;
 }
 void setCorridorPassable(std::size_t block, Bool passable) {
  assert(block < m_corridor.size());
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
  if(m_completeExecuting)m_completeCorridorWritten=true;
#endif
  m_corridor[block] = passable ? 1 : 0;
 }
 Bool corridorPassable(std::size_t block) const {
  assert(block < m_corridor.size());
  return m_corridor[block] != 0;
 }
};
inline PathfindSearchContext& mainPathfindSearchContext() {
 static PathfindSearchContext context;
 return context;
}
// GeneralsX @refactor Codex 27/10/2026 Cell and corridor helpers use the selected scratch owner; map lifetime uses main storage.
inline PathfindSearchContext& activePathfindSearchContext() {
 if (auto* selected=SearchContextBinding<PathfindSearchContext>::current()) return *selected;
 return mainPathfindSearchContext();
}
#ifndef GENERALS_ZH_SEARCH_CONTEXT
inline PathfindSearchNodes& mainPathfindSearchNodes() { return mainPathfindSearchContext(); }
#endif

/**
 * This represents one cell in the pathfinding grid.
 * These cells categorize the world into idealized cellular states,
 * and are also used for efficient A* pathfinding.
 * @todo Optimize memory usage of pathfind grid.
 */
class PathfindCell
{
	friend class PathfindCellList;
public:

	enum CellType
	{
		CELL_CLEAR		= 0x00,									///< clear, unobstructed ground
		CELL_WATER		= 0x01,									///< water area
		CELL_CLIFF		= 0x02,									///< steep altitude change
		CELL_RUBBLE		= 0x03,									///< Cell is occupied by rubble.
		CELL_OBSTACLE	= 0x04,									///< Occupied by a structure
		CELL_BRIDGE_IMPASSABLE = 0x05,				///< Piece of a bridge that is impassable.
		CELL_IMPASSABLE = 0x06								///< Just plain impassable except for aircraft.
	};

	enum CellFlags
	{
		NO_UNITS		= 0x00,						///< No units in this cell.
		UNIT_GOAL		= 0x01,						///< A unit is heading to this cell.
		UNIT_PRESENT_MOVING	= 0x02,		///< A unit is moving through this cell.
		UNIT_PRESENT_FIXED	= 0x03,		///< A unit is stationary in this cell.
		UNIT_GOAL_OTHER_MOVING	= 0x05		///< A unit is moving through this cell, and another unit has this as it's goal.
	};

	/// reset the cell
	void reset();

	PathfindCell();
	~PathfindCell();
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 // GeneralsX @performance Codex 29/10/2026 Register each ground/bridge/wall allocation once; reset() preserves its identity.
 static void registerSearchCells(PathfindCell* cells,unsigned count);
 unsigned searchIndex()const{return m_searchIndex;}
#endif

	Bool setTypeAsObstacle( Object *obstacle, Bool isFence, const ICoord2D &pos );				///< flag this cell as an obstacle, from the given one
	Bool removeObstacle( Object *obstacle );				///< unflag this cell as an obstacle, from the given one
	void setType( CellType type );	///< set the cell type
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
 // GeneralsX @feature Codex 27/10/2026 Compare permanent values exactly, excluding padding and all search scratch.
 std::array<unsigned, 19> permanentSearchValues() const {
  return {{static_cast<unsigned>(m_info != nullptr), static_cast<unsigned>(m_obstacleID), m_obstacleIsFence, m_obstacleIsTransparent,
   m_zone, m_aircraftGoal, m_pinched, m_type, m_flags, m_connectsToLayer, m_layer,
   static_cast<unsigned>(getGoalUnit()), static_cast<unsigned>(getGoalAircraft()), static_cast<unsigned>(getPosUnit()),
   static_cast<unsigned>(m_info ? m_info->m_pos.x : 0), static_cast<unsigned>(m_info ? m_info->m_pos.y : 0),
   static_cast<unsigned>(isObstacleFence()), static_cast<unsigned>(isObstacleTransparent()), static_cast<unsigned>(getObstacleID())}};
 }
#endif
	CellType getType() const { return (CellType)m_type; }				///< get the cell type
	CellFlags getFlags() const { return (CellFlags)m_flags; }				///< get the cell type
	Bool isAircraftGoal() const {return m_aircraftGoal != 0;}

	Bool isObstaclePresent( ObjectID objID ) const;					///< return true if the given object ID is registered as an obstacle in this cell
#if RETAIL_COMPATIBLE_PATHFINDING_ALLOCATION
	// TheSuperHackers @info isObstructionInvalid() and clearObstruction() only used during retail compatible pathfinding failover cleanup
	Bool isObstructionInvalid() const { return m_obstacleID != INVALID_ID && m_info == nullptr && (m_type == CELL_OBSTACLE || m_type == CELL_IMPASSABLE); }
	void clearObstruction() { m_type = CELL_CLEAR; m_obstacleID = INVALID_ID; m_obstacleIsFence = false; m_obstacleIsTransparent = false; }
#endif

	inline Bool isObstacleTransparent() const;
	inline Bool isObstacleFence() const;

	/// Return estimated cost from given cell to reach goal cell
	UnsignedInt costToGoal( PathfindCell *goal );

	UnsignedInt costToHierGoal( PathfindCell *goal );

	UnsignedInt costSoFar( PathfindCell *parent );

#if RETAIL_COMPATIBLE_PATHFINDING
	// Forward insertion sort that is 100% retail compatible
	void forwardInsertionSortRetailCompatible(PathfindCellList& list);
#endif

	// Forward insertion sort, in ascending cost order
	void forwardInsertionSort(PathfindCellList& list);

	// Reverse insertion sort, in ascending cost order
	void reverseInsertionSort(PathfindCellList& list);

	/// put self on "open" list in ascending cost order
	void putOnSortedOpenList( PathfindCellList &list );

	/// remove self from "open" list
	void removeFromOpenList( PathfindCellList &list );

	/// put self on "closed" list, return new list
	void putOnClosedList( PathfindCellList &list );

	/// remove self from "closed" list
	void removeFromClosedList( PathfindCellList &list );

	/// remove all cells from closed list.
	static Int releaseClosedList( PathfindCellList &list );

	/// remove all cells from closed list.
	static Int releaseOpenList( PathfindCellList &list );

	inline PathfindCell *getNextOpen() {return searchInfo()->search().m_nextOpen?searchInfo()->search().m_nextOpen->m_cell: nullptr;}
	inline PathfindCell *getPrevOpen() {return searchInfo()->search().m_prevOpen?searchInfo()->search().m_prevOpen->m_cell: nullptr;}

	inline UnsignedShort getXIndex() const {return searchInfo()->m_pos.x;}
	inline UnsignedShort getYIndex() const {return searchInfo()->m_pos.y;}

	inline Bool isBlockedByAlly() const;
	inline void setBlockedByAlly(Bool blocked);

	inline Bool getOpen() const {return searchInfo()->search().m_open;}
	inline Bool getClosed() const {return searchInfo()->search().m_closed;}
	inline UnsignedInt getCostSoFar() const {return searchInfo()->search().m_costSoFar;}
	inline UnsignedInt getTotalCost() const {return searchInfo()->search().m_totalCost;}

	inline UnsignedInt getTotalCostDifference(PathfindCell& other) const;

	inline void setCostSoFar(UnsignedInt cost) { if( searchInfo() ) searchInfo()->search().m_costSoFar = cost;}
	inline void setTotalCost(UnsignedInt cost) { if( searchInfo() ) searchInfo()->search().m_totalCost = cost;}

	void setParentCell(PathfindCell* parent);
	void clearParentCell();
	void setParentCellHierarchical(PathfindCell* parent);
	inline PathfindCell* getParentCell() const {return searchInfo() ? searchInfo()->search().m_pathParent ? searchInfo()->search().m_pathParent->m_cell : nullptr : nullptr;}

	Bool startPathfind( PathfindCell *goalCell );
	Bool getPinched() const {return m_pinched;}
	void setPinched(Bool pinch) {m_pinched = pinch;	}

 // Search admission is separate from persistent unit/obstacle allocation.
 PathfindSearchRecord* searchInfo() const {
#ifdef GENERALS_ZH_SEARCH_CONTEXT
  auto& context = activePathfindSearchContext();
  if (auto* record = context.findRecord(this)) return record;
  // Persistent cells historically already had info: materialize private scratch without new capacity credit.
  return m_info ? context.allocateRecord(const_cast<PathfindCell*>(this), m_info->m_pos, true) : nullptr;
#else
  return m_info;
#endif
 }
 Bool hasSearchInfo() const { return searchInfo() != nullptr; }
 Bool allocateSearchInfo(const ICoord2D& pos) {
#ifdef GENERALS_ZH_SEARCH_CONTEXT
  return activePathfindSearchContext().allocateRecord(this, pos, m_info != nullptr) != nullptr;
#else
  return allocateInfo(pos);
#endif
 }
 void releaseSearchInfo();
	Bool allocateInfo(const ICoord2D &pos);
	void releaseInfo();
	Bool hasInfo() const {return m_info!=nullptr;}
	zoneStorageType getZone() const {return m_zone;}
	void setZone(zoneStorageType zone) {m_zone = zone;}
	void setGoalUnit(ObjectID unit, const ICoord2D &pos );
	void setGoalAircraft(ObjectID unit, const ICoord2D &pos );
	void setPosUnit(ObjectID unit, const ICoord2D &pos );
	inline ObjectID getGoalUnit() const {ObjectID id = m_info?m_info->m_goalUnitID:INVALID_ID; return id;}
	inline ObjectID getGoalAircraft() const {ObjectID id = m_info?m_info->m_goalAircraftID:INVALID_ID; return id;}
	inline ObjectID getPosUnit() const {ObjectID id = m_info?m_info->m_posUnitID:INVALID_ID; return id;}

	inline ObjectID getObstacleID() const;

	void setLayer( PathfindLayerEnum layer ) { m_layer = layer; }	///< set the cell layer
	PathfindLayerEnum getLayer() const { return (PathfindLayerEnum)m_layer; }				///< get the cell layer

	void setConnectLayer( PathfindLayerEnum layer ) { m_connectsToLayer = layer; }	///< set the cell layer	connect id
	PathfindLayerEnum getConnectLayer() const { return (PathfindLayerEnum)m_connectsToLayer; }				///< get the cell layer connect id

private:
	PathfindCellInfo *m_info;
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 unsigned m_searchIndex=SearchCellIndices::invalid;
#endif
	ObjectID m_obstacleID;	                  ///< the object ID who overlaps this cell
	UnsignedInt m_blockedByAlly : 1;          ///< True if this cell is blocked by an allied unit.
	UnsignedInt m_obstacleIsFence : 1;        ///< True if occupied by a fence.
	UnsignedInt m_obstacleIsTransparent : 1;  ///< True if obstacle is transparent (undefined if obstacleid is invalid)

	zoneStorageType m_zone : 14;              ///< Zone. Each zone is a set of adjacent terrain type.  If from & to in the same zone, you can successfully pathfind.  If not,
	                                          /// you still may be able to if you can cross multiple terrain types.
	UnsignedShort m_aircraftGoal : 1;         ///< This is an aircraft goal cell.
	UnsignedShort m_pinched : 1;              ///< This cell is surrounded by obstacle cells.
	UnsignedByte m_type : 4;                  ///< what type of cell terrain this is.
	UnsignedByte m_flags : 4;                 ///< what type of units are in or moving through this cell.
	UnsignedByte m_connectsToLayer : 4;       ///< This cell can pathfind onto this layer, if > LAYER_TOP.
	UnsignedByte m_layer : 4;                 ///< Layer of this cell.
};

typedef PathfindCell *PathfindCellP;
#ifdef GENERALS_ZH_SEARCH_CONTEXT
 inline unsigned pathfindCellSearchIndex(const PathfindCell* cell){return cell->searchIndex();}
#endif


// how close a unit has to be in z to interact with the layer.
#define LAYER_Z_CLOSE_ENOUGH_F 10.0f
/**
 * This class represents a bridge in the map. This is effectively
 * a sub-rectangle of the big pathfind map.
 */
class PathfindLayer
{
public:
	PathfindLayer();
	~PathfindLayer();
public:
	void reset();
	Bool init(Bridge *theBridge, PathfindLayerEnum layer);
	void allocateCells(const IRegion2D *extent);
	void allocateCellsForWallLayer(const IRegion2D *extent, ObjectID *wallPieces, Int numPieces);
	void classifyCells();
	void classifyWallCells(ObjectID *wallPieces, Int numPieces);
	Bool setDestroyed(Bool destroyed);
	Bool isUnused(); // True if it doesn't contain a bridge.
	Bool isDestroyed() {return m_destroyed;} // True if it has been destroyed.
	PathfindCell *getCell(Int x, Int y);
	Int getZone() {return m_zone;}
	void setZone(Int zone) {m_zone = zone;}
	void applyZone(); // Propagates m_zone to all cells.
	void getStartCellIndex(ICoord2D *start) {*start = m_startCell;}
	void getEndCellIndex(ICoord2D *end) {*end = m_endCell;}

	ObjectID getBridgeID();
	Bool connectsZones(PathfindZoneManager *zm, const LocomotorSet& locomotorSet,Int zone1, Int zone2);
	Bool isPointOnWall(ObjectID *wallPieces, Int numPieces, const Coord3D *pt);

#if defined(RTS_DEBUG)
	void doDebugIcons() ;
#endif
protected:
	void classifyLayerMapCell( Int i, Int j , PathfindCell *cell, Bridge *theBridge);
	void classifyWallMapCell( Int i, Int j, PathfindCell *cell , ObjectID *wallPieces, Int numPieces);

private:
	PathfindCell *m_blockOfMapCells;		///< Pathfinding map - contains iconic representation of the map
	PathfindCell **m_layerCells;		///< Pathfinding map indexes - contains matrix indexing into the map.
	Int m_width;		// Number of cells in x
	Int m_height;		// Number of cells in y
	Int m_xOrigin;	// Index of first cell in x
	Int m_yOrigin;	// Index of first cell in y
	ICoord2D m_startCell; // pathfind cell indexes for center cell on the from side.
	ICoord2D m_endCell; // pathfind cell indexes for center cell on the to side.

	PathfindLayerEnum m_layer;
	Int m_zone;			// Whole bridge is in same zone.
	Bridge *m_bridge; // Corresponding bridge in TerrainLogic.
	Bool m_destroyed;


};


#define PATHFIND_CELL_SIZE		10
#define PATHFIND_CELL_SIZE_F	10.0f

enum { PATHFIND_QUEUE_LEN=512};

struct TCheckMovementInfo;

/**
 * This class is a helper class for zone manager.  It maintains information regarding the
 * LocomotorSurfaceTypeMask equivalencies within a ZONE_BLOCK_SIZE x ZONE_BLOCK_SIZE area of
 * cells.  This is used in hierarchical pathfinding to find the best coarse path at the
 * block level.
 */
class ZoneBlock
{
public:
	ZoneBlock();
	~ZoneBlock();  // not virtual, please don't override without making virtual.  jba.

	void blockCalculateZones(	PathfindCell **map, PathfindLayer layers[], const IRegion2D &bounds);	///< Does zone calculations.
	zoneStorageType getEffectiveZone(LocomotorSurfaceTypeMask acceptableSurfaces, Bool crusher, zoneStorageType zone) const;

#ifndef GENERALS_ZH_SEARCH_CONTEXT
	void clearMarkedPassable() {m_markedPassable = false;}
	Bool isPassable() {return m_markedPassable;}
	void setPassable(Bool pass) {m_markedPassable = pass;}
#endif

	Bool getInteractsWithBridge() const {return m_interactsWithBridge;}
	void setInteractsWithBridge(Bool interacts) {m_interactsWithBridge = interacts;}

protected:
	void allocateZones();
	void freeZones();

protected:
	ICoord2D		m_cellOrigin;

	zoneStorageType m_firstZone; // First zone in this block.
	UnsignedShort m_numZones;	 // Number of zones in this block.  If == 1, there is only one zone, and
														 // no zone equivalency arrays will be allocated.

	UnsignedShort m_zonesAllocated;
	zoneStorageType *m_groundCliffZones;
	zoneStorageType *m_groundWaterZones;
	zoneStorageType *m_groundRubbleZones;
	zoneStorageType *m_crusherZones;
	Bool					m_interactsWithBridge;
#ifndef GENERALS_ZH_SEARCH_CONTEXT
	Bool					m_markedPassable;
#endif
};
typedef ZoneBlock *ZoneBlockP;

/**
 * This class manages the zones in the map.  A zone is an area in the map that
 * is one contiguous type of terrain (clear, cliff, water, building).  If
 * a unit is in a zone, and wants to move to another location, the destination
 * zone has to be the same, or it can't get there.
 * There are equivalency tables for meta-zones.  For example, an amphibious craft can
 * travel through water and clear cells.
 */
class PathfindZoneManager
{
public:
	enum {INITIAL_ZONES = 256};
	enum {ZONE_BLOCK_SIZE = 10};	// Zones are calculated in blocks of 20x20.  This way, the raw zone numbers can be used to
	enum {UNINITIALIZED_ZONE = 0};
																// compute hierarchically between the 20x20 blocks of cells. jba.
	PathfindZoneManager();
	~PathfindZoneManager();

	void reset();

	Bool needToCalculateZones() const {return m_nextFrameToCalculateZones <= TheGameLogic->getFrame() ;} ///< Returns true if the zones need to be recalculated.
	void markZonesDirty() ; ///< Called when the zones need to be recalculated.
	void updateZonesForModify( PathfindCell **map,  PathfindLayer layers[], const IRegion2D &structureBounds, const IRegion2D &globalBounds ) ; ///< Called to recalculate an area when a structure has been removed.
	// GeneralsX @feature Codex 29/10/2026 Optional main-owned profiling measures rebuild passes without changing zone calculation.
	void calculateZones(	PathfindCell **map, PathfindLayer layers[], const IRegion2D &bounds
#ifdef GENERALS_ZH_PATH_TIMING
		, PathSearchTiming* timing = nullptr
#endif
	);	///< Does zone calculations.
	zoneStorageType getEffectiveZone(LocomotorSurfaceTypeMask acceptableSurfaces, Bool crusher, zoneStorageType zone) const;
	zoneStorageType getEffectiveTerrainZone(zoneStorageType zone) const;

	void getExtent(ICoord2D &extent) const {extent = m_zoneBlockExtent;}

	/// return zone relative the the block zone that this cell resides in.
	zoneStorageType getBlockZone(LocomotorSurfaceTypeMask acceptableSurfaces, Bool crusher, Int cellX, Int cellY, PathfindCell **map) const;
	void allocateBlocks(const IRegion2D &globalBounds);

	void clearPassableFlags();
	Bool isPassable(Int cellX, Int cellY) const;
	Bool clipIsPassable(Int cellX, Int cellY) const;
	void setPassable(Int cellX, Int cellY, Bool passable);

	void setAllPassable();

	void setBridge(Int cellX, Int cellY, Bool bridge);
	Bool interactsWithBridge(Int cellX, Int cellY) const;

private:
	void allocateZones();
	void freeZones();
	void freeBlocks();

private:
	ZoneBlock			*m_blockOfZoneBlocks;			///< Zone blocks - Info for hierarchical pathfinding at a "blocky" level.
	ZoneBlock			**m_zoneBlocks;						///< Zone blocks as a matrix - contains matrix indexing into the map.
	ICoord2D			m_zoneBlockExtent;				///< Zone block extents. Not the same scale as the pathfind extents.

	UnsignedShort m_maxZone;								///< Max zone used.
	UnsignedInt		m_nextFrameToCalculateZones;		///< When should I recalculate, next?.
	UnsignedShort m_zonesAllocated;
	zoneStorageType *m_groundCliffZones;
	zoneStorageType *m_groundWaterZones;
	zoneStorageType *m_groundRubbleZones;
	zoneStorageType *m_terrainZones;
	zoneStorageType *m_crusherZones;
	zoneStorageType *m_hierarchicalZones;
};

/**
 * The pathfinding services interface provides access to the 3 expensive path find calls:
 * findPath, findClosestPath, and findAttackPath.
 * It is only available to units when their ai interface doPathfind method is called.
 * This allows the pathfinder to spread out the pathfinding over a number of frames
 * when a lot of units are trying to pathfind all at the same time.
 */
class PathfindServicesInterface {
public:
	virtual Path *findPath( Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from,
		const Coord3D *to )=0;	///< Find a short, valid path between given locations
	/** Find a short, valid path to a location NEAR the to location.
		This succeeds when the destination is unreachable (like inside a building).
		If the destination is unreachable, it will adjust the to point.  */
	virtual Path *findClosestPath( Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from,
		Coord3D *to, Bool blocked, Real pathCostMultiplier, Bool moveAllies )=0;

	/** Find a short, valid path to a location that obj can attack victim from.  */
	virtual Path *findAttackPath( const Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from,
		const Object *victim, const Coord3D* victimPos, const Weapon *weapon )=0;

	/** Patch to the exiting path from the current position, either because we became blocked,
  or because we had to move off the path to avoid other units. */
	virtual Path *patchPath( const Object *obj, const LocomotorSet& locomotorSet,
		Path *originalPath, Bool blocked ) = 0;

	/** Find a short, valid path to a location that is away from the repulsors.  */
	virtual Path *findSafePath( const Object *obj, const LocomotorSet& locomotorSet,
		const Coord3D *from, const Coord3D* repulsorPos1, const Coord3D* repulsorPos2, Real repulsorRadius ) = 0;

};

// GeneralsX @refactor Codex 27/10/2026 Owned ordinary fine-search policy; world relationships stay live.
struct PathfindMovementSettings {
	LocomotorSurfaceTypeMask surfaces;
	Bool downhillOnly;
	PathfindLayerEnum layer;
	Bool crusher;
	Bool throughUnits;
	Bool dozer;
	Bool vehicle;
	Int radius;
	Bool centerInCell;
	Bool human;
};
struct PathfindMovementInput;

// GeneralsX @feature Codex 27/10/2026 Closest-loop policy and preparation decisions are explicit result dependencies.
struct PathfindClosestSettings {
 Bool blocked;
 Real pathCostMultiplier;
 Bool moveAllies;
 Bool goalOnObstacle;
 Bool startedStuck;
 Bool gotHierarchicalPath;
 ObjectID initialIgnored;
 Bool operator==(const PathfindClosestSettings& other) const {
  return blocked==other.blocked && pathCostMultiplier==other.pathCostMultiplier && moveAllies==other.moveAllies &&
   goalOnObstacle==other.goalOnObstacle && startedStuck==other.startedStuck &&
   gotHierarchicalPath==other.gotHierarchicalPath && initialIgnored==other.initialIgnored;
 }
};

/**
 * The Pathfinding engine itself.
 */
class Pathfinder : PathfindServicesInterface, public Snapshot
{
// The following routines are private, but available through the doPathfind callback to aiInterface. jba.
private:
	virtual Path *findPath( Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from, const Coord3D *to) override;	///< Find a short, valid path between given locations
	/** Find a short, valid path to a location NEAR the to location.
		This succeeds when the destination is unreachable (like inside a building).
		If the destination is unreachable, it will adjust the to point.  */
	virtual Path *findClosestPath( Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from,
		Coord3D *to, Bool blocked, Real pathCostMultiplier, Bool moveAllies ) override;

	/** Find a short, valid path to a location that obj can attack victim from.  */
	virtual Path *findAttackPath( const Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from,
		const Object *victim, const Coord3D* victimPos, const Weapon *weapon ) override;

	/** Find a short, valid path to a location that is away from the repulsors.  */
	virtual Path *findSafePath( const Object *obj, const LocomotorSet& locomotorSet,
		const Coord3D *from, const Coord3D* repulsorPos1, const Coord3D* repulsorPos2, Real repulsorRadius ) override;

	/** Patch to the exiting path from the current position, either because we became blocked,
  or because we had to move off the path to avoid other units. */
	virtual Path *patchPath( const Object *obj, const LocomotorSet& locomotorSet,
		Path *originalPath, Bool blocked ) override;

public:
	Pathfinder();
	~Pathfinder() ;

	void reset();														///< Reset system in preparation for new map

	// --------------- inherited from Snapshot interface --------------
	virtual void crc( Xfer *xfer ) override;
	virtual void xfer( Xfer *xfer ) override;
	virtual void loadPostProcess() override;

	Bool clientSafeQuickDoesPathExist( const LocomotorSet& locomotorSet, const Coord3D *from, const Coord3D *to );  ///< Can we build any path at all between the locations	(terrain & buildings check - fast)
	Bool clientSafeQuickDoesPathExistForUI( const LocomotorSet& locomotorSet, const Coord3D *from, const Coord3D *to );  ///< Can we build any path at all between the locations	(terrain only - fast)
	Bool slowDoesPathExist( Object *obj, const Coord3D *from,
		const Coord3D *to, ObjectID ignoreObject=INVALID_ID );  ///< Can we build any path at all between the locations	(terrain, buildings & units check - slower)

	Bool queueForPath(ObjectID id);	 ///< The object wants to request a pathfind, so put it on the list to process.
	void processPathfindQueue(); ///< Process some or all of the queued pathfinds.
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
 // GeneralsX @feature Codex 27/10/2026 Called only by the actual AI no-path branch after the caller's ordinary attempt has failed.
 void confirmParallelFallback(const Object* obj, const LocomotorSet& locomotorSet,
  const Coord3D& from, const Coord3D& to, Bool blocked);
#endif
	void forceMapRecalculation();	///< Force pathfind map recomputation. If region is given, only that area is recomputed

	/** Returns an aircraft path to the goal.  */
	Path *getAircraftPath( const Object *obj, const Coord3D *to);
	Path *findGroundPath( const Coord3D *from, const Coord3D *to, Int pathRadius,
		Bool crusher);	///< Find a short, valid path of the desired width on the ground.

	void addObjectToPathfindMap( class Object *obj );				///< Classify the given object's cells in the map
	void removeObjectFromPathfindMap( class Object *obj );	///< De-classify the given object's cells in the map

	void removeUnitFromPathfindMap( Object *obj );	///< De-classify the given mobile unit's cells in the map
	void updateGoal( Object *obj, const Coord3D *newGoalPos, PathfindLayerEnum layer);		///< Update the given mobile unit's cells in the map
	void updateAircraftGoal( Object *obj, const Coord3D *newGoalPos);		///< Update the given aircraft unit's cells in the map
	void removeGoal( Object *obj);		///< Removes the given mobile unit's goal cells in the map
	void updatePos( Object *obj, const Coord3D *newPos);		///< Update the given mobile unit's cells in the map
	void removePos( Object *obj);		///< Removes the unit's position cells from the map

	Bool moveAllies(Object *obj, Path *path);

	// NOTE - The object MUST NOT MOVE between the call to createAWall... and removeWall...
	// or BAD THINGS will happen.  jba.
	void createAWallFromMyFootprint( Object *obj ) {internal_classifyObjectFootprint(obj, true);}  // Temporarily treat this object as an obstacle.
	void removeWallFromMyFootprint( Object *obj ){internal_classifyObjectFootprint(obj, false);}   // Undo createAWallFromMyFootprint.

	Path *getMoveAwayFromPath(Object *obj, Object *otherObj, Path *pathToAvoid, Object *otherObj2, Path *pathToAvoid2);

	void changeBridgeState( PathfindLayerEnum layer, Bool repaired );

	Bool findBrokenBridge(const LocomotorSet &locomotorSet, const Coord3D *from, const Coord3D *to, ObjectID *bridgeID);

	void newMap();

	PathfindCell *getCell( PathfindLayerEnum layer, Int x, Int y );							///< Return the cell at grid coords (x,y)
	PathfindCell *getCell( PathfindLayerEnum layer, const Coord3D *pos );				///< Given a position, return associated grid cell
	PathfindCell *getClippedCell( PathfindLayerEnum layer, const Coord3D *pos );				///< Given a position, return associated grid cell
	void clip(Coord3D *from, Coord3D *to);
	Bool worldToCell( const Coord3D *pos, ICoord2D *cell );	///< Given a world position, return grid cell coordinate

	const ICoord2D *getExtent() const {return &m_extent.hi;}

	void setIgnoreObstacleID( ObjectID objID );					///< if non-zero, the pathfinder will ignore the given obstacle

	Bool validMovementPosition( Bool isCrusher, LocomotorSurfaceTypeMask acceptableSurfaces, PathfindCell *toCell, PathfindCell *fromCell = nullptr );		///< Return true if given position is a valid movement location
	Bool validMovementPosition( Bool isCrusher, PathfindLayerEnum layer, const LocomotorSet& locomotorSet, Int x, Int y );					///< Return true if given position is a valid movement location
	Bool validMovementPosition( Bool isCrusher, PathfindLayerEnum layer, const LocomotorSet& locomotorSet, const Coord3D *pos );		///< Return true if given position is a valid movement location
	Bool validMovementTerrain( PathfindLayerEnum layer, const Locomotor* locomotor, const Coord3D *pos );		///< Return true if given position is a valid movement location

	Locomotor* chooseBestLocomotorForPosition(PathfindLayerEnum layer,  LocomotorSet* locomotorSet, const Coord3D* pos );

	Bool isViewBlockedByObstacle(const Object* obj, const Object* objOther);	///< Return true if the straight line between the given points contains any obstacle, and thus blocks vision

	Bool isAttackViewBlockedByObstacle(const Object* obj, const Coord3D& attackerPos,  const Object* victim, const Coord3D& victimPos);	///< Return true if the straight line between the given points contains any obstacle, and thus blocks vision

	Bool isLinePassable( const Object *obj, LocomotorSurfaceTypeMask acceptableSurfaces,
		PathfindLayerEnum layer, const Coord3D& startWorld, const Coord3D& endWorld,
		Bool blocked, Bool allowPinched );	///< Return true if the straight line between the given points is passable

	void moveAlliesAwayFromDestination( Object *obj,const Coord3D& destination);

	Bool isGroundPathPassable( Bool isCrusher, const Coord3D& startWorld, PathfindLayerEnum startLayer,
		const Coord3D& endWorld, Int pathDiameter);	///< Return true if the straight line between the given points is passable

	// for debugging
	const Coord3D *getDebugPathPosition();
	void setDebugPathPosition( const Coord3D *pos );
	Path *getDebugPath();
	void setDebugPath( Path *debugpath );

#if RETAIL_COMPATIBLE_PATHFINDING
	void forceCleanCells();
#endif
	void beginSearchState();
	void cleanOpenAndClosedLists();

	// Adjusts the destination to a spot near dest that is not occupied by other units.
	Bool adjustDestination(Object *obj, const LocomotorSet& locomotorSet,
		Coord3D *dest, const Coord3D *groupDest=nullptr);

	// Adjusts the destination to a spot near dest for landing that is not occupied by other units.
	Bool adjustToLandingDestination(Object *obj, Coord3D *dest);

	// Adjusts the destination to a spot that can attack target that is not occupied by other units.
	Bool adjustTargetDestination(const Object *obj, const Object *target, const Coord3D *targetPos,
		const Weapon *weapon, Coord3D *dest);

	// Adjusts destination to a spot near dest that is possible to path to.
	Bool adjustToPossibleDestination(Object *obj, const LocomotorSet& locomotorSet, Coord3D *dest);

	void snapPosition(Object *obj, Coord3D *pos); // Snaps the current position to it's grid location.
	void snapClosestGoalPosition(Object *obj, Coord3D *pos); // Snaps the current position to a good goal position.
	Bool goalPosition(Object *obj, Coord3D *pos); // Returns the goal position on the grid.

	PathfindLayerEnum addBridge(Bridge *theBridge); // Adds a bridge layer, and returns the layer id.

	void addWallPiece(Object *wallPiece); // Adds a wall piece.
	void removeWallPiece(Object *wallPiece);  // Removes a wall piece.
	Real getWallHeight() {return m_wallHeight;}
	Bool isPointOnWall(const Coord3D *pos);

	void updateLayer(Object *obj, PathfindLayerEnum layer); ///< Updates object's layer.

	static void classifyMapCell( Int x, Int y, PathfindCell *cell);					///< Classify the given map cell
	Int clearCellForDiameter( Bool crusher, Int cellX, Int cellY, PathfindLayerEnum layer, Int pathDiameter );		///< Return true if given position is a valid movement location

protected:
	// GeneralsX @refactor Codex 27/10/2026 First owned input boundary; not a complete worker request.
#ifdef GENERALS_ZH_SEARCH_CONTEXT
	struct OrdinaryPathRequest {
		Coord3D from;
		Coord3D to;
	};
#endif
	Path *findPathWithInputs(Object *obj, const LocomotorSet& locomotorSet,
		const Coord3D *from, const Coord3D *to);
	// GeneralsX @refactor Codex 27/10/2026 Pointers remain valid only while the selected search phase owns its records.
	struct OrdinarySearchOutcome {
		PathfindCell *lastCell;
		Int cellsExamined;
		Bool found;
	};
 struct ClosestSearchOutcome {
  PathfindCell* lastCell;
  PathfindCell* closestCell;
  Int cellsExamined;
  Bool reachedGoal;
 };
#ifdef GENERALS_ZH_EXCLUSIVE_PATH_WORKER
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
 friend struct PathfindParallelBatch;
 friend struct PathfindParallelJob;
 PathfindParallelBatch* m_parallelBatch;
#ifdef GENERALS_ZH_PATH_TIMING
 PathSearchTiming m_pathTiming;
 PathSearchTiming& searchTiming();
#endif
 unsigned long long m_parallelWorldEpoch;
// GeneralsX @performance Codex 30/10/2026 Inspect queue spans without allocating another result buffer or search arena.
#ifdef GENERALS_ZH_PATH_LOOKAHEAD
 PathLookaheadWindow<PATHFIND_QUEUE_LEN> m_lookaheadWindow;
#ifdef GENERALS_ZH_PATH_TIMING
 PathLookaheadProfile m_lookaheadProfile;
#endif
#endif
 void prepareParallelBatch();
 void clearParallelBatch();
 void observeParallelCell(PathfindCell* cell);
 Real searchGroundHeight(Real x, Real y);
 PathfindParallelJob* takeParallelResult(const Object* obj, const LocomotorSet& locomotorSet,
  const Coord3D& from, const Coord3D& to, const Coord3D* repulsor2, Real repulsorRadius,
  PathfindCell* start, PathfindCell* goal, const ICoord2D& startIndex, const PathfindMovementSettings& settings,
  const PathfindClosestSettings* closest=nullptr, Bool complete=false);
#ifdef GENERALS_ZH_COMPLETE_PATH_WORKER
 Bool takeCompletePath(const Object* obj,const LocomotorSet& locomotorSet,const Coord3D& from,const Coord3D& to,
  const Coord3D* repulsor2,Real repulsorRadius,const PathfindClosestSettings* closest,Path*& path,Coord3D* adjustedTo=nullptr);
#ifdef GENERALS_ZH_PATH_WORKER_POOL
 void executeCompletePath(PathfindParallelJob& job,PathfindSearchContext& context);
#else
 void executeCompletePath(PathfindParallelJob& job);
#endif
 PathfindLayerEnum searchDestinationLayer(const Coord3D* pos);
 Real searchLayerHeight(Real x,Real y,PathfindLayerEnum layer);
 void observeParallelObject(ObjectID id);
#endif
 void invalidateParallelResults() {++m_parallelWorldEpoch;}
#endif
	PathfindExclusiveWorker *m_exclusiveWorker;
	Bool m_exclusiveWorkerUnavailable;
#endif
	OrdinarySearchOutcome runOrdinarySearchLoop(PathfindCell *parentCell, PathfindCell *goalCell,
		const PathfindMovementInput& movement, Bool isHuman, Bool centerInCell, Int radius,
		const ICoord2D& startCellNdx, const Object *obj);
 // GeneralsX @feature Codex 29/10/2026 Escape loops return to their owning API; complete participants also finalize privately.
 OrdinarySearchOutcome runSafeSearchLoop(PathfindCell* parentCell, const PathfindMovementInput& movement,
  Bool isHuman, Bool centerInCell, Int radius, const ICoord2D& startIndex,
  const Coord3D& repulsor1, const Coord3D& repulsor2, Real repulsorRadius);
 // GeneralsX @feature Codex 29/10/2026 Closest scoring is shared by fine-only dispatch and complete API execution.
 ClosestSearchOutcome runClosestSearchLoop(PathfindCell* parentCell, PathfindCell* goalCell,
  const PathfindMovementInput& movement, Bool isHuman, Bool centerInCell, Int radius,
  const ICoord2D& startIndex, const PathfindClosestSettings& closest);
	virtual Path *internalFindPath( Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from, const Coord3D *to);	///< Find a short, valid path between given locations
	Path *findHierarchicalPath( Bool isHuman, const LocomotorSet& locomotorSet, const Coord3D *from, const Coord3D *to, Bool crusher);
	Path *findClosestHierarchicalPath( Bool isHuman, const LocomotorSet& locomotorSet, const Coord3D *from, const Coord3D *to, Bool crusher);
	Path *internal_findHierarchicalPath( Bool isHuman, const LocomotorSurfaceTypeMask locomotorSurface, const Coord3D *from, const Coord3D *to, Bool crusher, Bool closestOK);
	void processHierarchicalCell( const ICoord2D &scanCell, const ICoord2D &deltaPathfindCell,
																PathfindCell *parentCell,
																PathfindCell *goalCell, zoneStorageType parentZone,
																zoneStorageType *examinedZones, Int &numExZones,
																Bool crusher, Int &cellCount);
	Bool checkForAdjust(Object *, const LocomotorSet& locomotorSet, Bool isHuman, Int cellX, Int cellY,
		PathfindLayerEnum layer, Int iRadius, Bool center,Coord3D *dest, const Coord3D *groupDest) ;
	Bool checkForLanding(Int cellX, Int cellY,
		PathfindLayerEnum layer, Int iRadius, Bool center,Coord3D *dest) ;
	Bool checkForTarget(const Object *obj, 	Int cellX, Int cellY, const Weapon *weapon,
																const Object *victim, const Coord3D *victimPos,
																Int iRadius, Bool center,Coord3D *dest) ;
	Bool checkForPossible(Bool isCrusher, Int fromZone,  Bool center, const LocomotorSet& locomotorSet,
		Int cellX, Int cellY, PathfindLayerEnum layer, Coord3D *dest, Bool startingInObstacle) ;
	void getRadiusAndCenter(const Object *obj, Int &iRadius, Bool &center);
	PathfindMovementSettings captureMovementSettings(const Object *obj, const LocomotorSet& locomotorSet,
		Int radius, Bool centerInCell, Bool human);
	Bool validMovementPosition(Bool crusher, PathfindLayerEnum layer,
		const PathfindMovementInput& movement, const Coord3D *pos);

	void adjustCoordToCell(Int cellX, Int cellY, Bool centerInCell, Coord3D &pos, PathfindLayerEnum layer);
#ifdef GENERALS_ZH_OCCUPANCY_WORKER
	PathOccupancy::Result evaluateOccupancyQuery(const Object *obj, const PathOccupancy::Input& input);
	PathfindOccupancyValidation *m_occupancyValidation;
	Bool m_occupancyValidationUnavailable;
	UnsignedInt m_occupancySamplesRemaining;
#endif
	Bool checkDestination(const Object *obj, Int cellX, Int cellY, PathfindLayerEnum layer, Int iRadius, Bool centerInCell);
	Bool checkForMovement(const Object *obj, TCheckMovementInfo &info);
	Bool segmentIntersectsTallBuilding(const PathNode *curNode, PathNode *nextNode,
		ObjectID ignoreBuilding, Coord3D *insertPos1, Coord3D *insertPos2, Coord3D *insertPos3);	///< Return true if the straight line between the given points intersects a tall building.
	Bool circleClipsTallBuilding(const Coord3D *from, const Coord3D *to, Real radius, ObjectID ignoreBuilding, Coord3D *adjustTo);	///< Return true if the circle at the end of the line between the given points intersects a tall building.

	enum {NO_ATTACK=0};
	Int examineNeighboringCells(PathfindCell *parentCell, PathfindCell *goalCell,
										const LocomotorSet& locomotorSet, Bool isHumanPlayer,
										Bool centerInCell, Int radius, const ICoord2D &startCellNdx,
										const Object *obj, Int attackDistance);

	Int examineNeighboringCellsWithMovement(PathfindCell *parentCell, PathfindCell *goalCell,
		const PathfindMovementInput& movement, Bool isHuman, Bool centerInCell, Int radius,
		const ICoord2D& startCellNdx, const Object *obj, Int attackDistance);

	Int checkPathCost(Object *obj, const LocomotorSet& locomotorSet, const Coord3D *from,
		const Coord3D *to);

	void tightenPath(Object *obj, const LocomotorSet& locomotorSet, Coord3D *from,
		const Coord3D *to);

	/**
		return 0 to continue iterating the line, nonzero to terminate the iteration.
		the nonzero result will be returned as the result of iterateCellsAlongLine().
		iterateCellsAlongLine will return zero if it completes.
	*/
	typedef Int (*CellAlongLineProc)(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
	Int iterateCellsAlongLine(const Coord3D& startWorld, const Coord3D& endWorld,
		PathfindLayerEnum layer, CellAlongLineProc proc, void* userData);

	Int iterateCellsAlongLine(const ICoord2D &start, const ICoord2D &end,
		PathfindLayerEnum layer, CellAlongLineProc proc, void* userData);

	static Int linePassableCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
	static Int groundPathPassableCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
	static Int lineBlockedByObstacleCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
	static Int tightenPathCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
	static Int attackBlockedByObstacleCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
 	static Int examineCellsCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
 	static Int groundCellsCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);
 	static Int moveAlliesDestinationCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);

	static Int segmentIntersectsBuildingCallback(Pathfinder* pathfinder, PathfindCell* from, PathfindCell* to, Int to_x, Int to_y, void* userData);

	void classifyMap();					///< Classify all cells in grid as obstacles, etc
	void classifyObjectFootprint( Object *obj, Bool insert );	/** Classify the cells under the given object
																																If 'insert' is true, object is being added
																																If 'insert' is false, object is being removed */
	void internal_classifyObjectFootprint( Object *obj, Bool insert );	/** Classify the cells under the given object
																																If 'insert' is true, object is being added
																																If 'insert' is false, object is being removed */
	void classifyFence( Object *obj, Bool insert );	/** Classify the cells under the given fence object. */
	void classifyUnitFootprint( Object *obj, Bool insert, Bool remove, Bool update );	/** Classify the cells under the given object If 'insert' is true, object is being added */
	/// Convert world coordinate to array index
	void worldToGrid( const Coord3D *pos, ICoord2D *cellIndex );

	Bool evaluateCell(PathfindCell* newCell, PathfindCell *parentCell,
									const LocomotorSet& locomotorSet,
									 Bool centerInCell, Int radius,
									 const Object *obj, Int attackDistance);

	Path *buildActualPath( const Object *obj, LocomotorSurfaceTypeMask acceptableSurfaces,
		const Coord3D *fromPos, PathfindCell *goalCell, Bool center, Bool blocked );	///< Work backwards from goal cell to construct final path
	Path *buildGroundPath( Bool isCrusher,const Coord3D *fromPos, PathfindCell *goalCell,
		Bool center, Int pathDiameter );	///< Work backwards from goal cell to construct final path
	Path *buildHierarchicalPath( const Coord3D *fromPos, PathfindCell *goalCell);	///< Work backwards from goal cell to construct final path

 // GeneralsX @refactor Codex 27/10/2026 Share the unchanged cell walk between legacy and owned route sinks.
 template<class RouteSink>
 void prependRouteCells(RouteSink* route, const Coord3D* fromPos, PathfindCell* goalCell, Bool center);
	void  prependCells( Path *path, const Coord3D *fromPos,
																	PathfindCell *goalCell, Bool center ); ///< Add pathfind cells to a path.

	void debugShowSearch( Bool pathFound );				///< Show all cells touched in the last search
	static LocomotorSurfaceTypeMask validLocomotorSurfacesForCellType(PathfindCell::CellType t);

	void checkChangeLayers(PathfindCell *parentCell);

	bool checkCellOutsideExtents(ICoord2D& cell);

#if defined(RTS_DEBUG)
	void doDebugIcons() ;
#endif

private:
 // GeneralsX @refactor Codex 26/10/2026 Route all search scratch through one serial owner.
 PathfindSearchBookkeeping& searchState() const {
#ifdef GENERALS_ZH_SEARCH_CONTEXT
  return activePathfindSearchContext();
#else
  return m_legacySearchState;
#endif
 }
#ifndef GENERALS_ZH_SEARCH_CONTEXT
 mutable PathfindSearchBookkeeping m_legacySearchState;
#endif

private:
	/// This uses WAY too much memory.  Should at least be array of pointers to cells w/ many fewer cells
	PathfindCell *m_blockOfMapCells;		///< Pathfinding map - contains iconic representation of the map
	PathfindCell **m_map;		///< Pathfinding map indexes - contains matrix indexing into the map.
	IRegion2D m_extent;														///< Grid extent limits
	IRegion2D m_logicalExtent;										///< Logical grid extent limits


	Bool m_isMapReady;														///< True if all cells of map have been classified

	Int m_frameToShowObstacles;										///< Time to redraw obstacles.  For debug output.

	Coord3D debugPathPos;													///< Used for visual debugging
	Path *debugPath;															///< Used for visual debugging


	PathfindZoneManager m_zoneManager;						///< Handles the pathfind zones.

	PathfindLayer m_layers[LAYER_LAST+1];

	ObjectID			m_wallPieces[MAX_WALL_PIECES];
	Int						m_numWallPieces;
	Real					m_wallHeight;

	Int						m_moveAlliesDepth;


	// Pathfind queue
	ObjectID			m_queuedPathfindRequests[PATHFIND_QUEUE_LEN];
	Int						m_queuePRHead;
	Int						m_queuePRTail;

#if RTS_ZEROHOUR && RETAIL_COMPATIBLE_CRC
public:
	Bool					m_classifyFenceZeroInit;
#endif
};


inline void Pathfinder::setIgnoreObstacleID( ObjectID objID )
{
	searchState().m_ignoreObstacleID = objID;
}

inline void Pathfinder::worldToGrid( const Coord3D *pos, ICoord2D *cellIndex )
{
	cellIndex->x = REAL_TO_INT(pos->x/PATHFIND_CELL_SIZE);
	cellIndex->y = REAL_TO_INT(pos->y/PATHFIND_CELL_SIZE);
}

inline Bool Pathfinder::validMovementPosition( Bool isCrusher, PathfindLayerEnum layer, const LocomotorSet& locomotorSet, Int x, Int y )
{
	return validMovementPosition( isCrusher, locomotorSet.getValidSurfaces(), getCell( layer, x, y ) );
}

inline Bool Pathfinder::validMovementPosition( Bool isCrusher, PathfindLayerEnum layer, const LocomotorSet& locomotorSet, const Coord3D *pos )
{

	Int x = REAL_TO_INT(pos->x/PATHFIND_CELL_SIZE);
	Int y = REAL_TO_INT(pos->y/PATHFIND_CELL_SIZE);

	return validMovementPosition( isCrusher, layer, locomotorSet, x, y );
}

inline const Coord3D *Pathfinder::getDebugPathPosition()
{
	return &debugPathPos;
}

inline void Pathfinder::setDebugPathPosition( const Coord3D *pos )
{
	debugPathPos = *pos;
}

inline Path *Pathfinder::getDebugPath()
{
	return debugPath;
}

inline void Pathfinder::addObjectToPathfindMap( class Object *obj )
{
	classifyObjectFootprint( obj, true );
}

inline void Pathfinder::removeObjectFromPathfindMap( class Object *obj )
{
	classifyObjectFootprint( obj, false );
}

inline PathfindCell *Pathfinder::getCell( PathfindLayerEnum layer, Int x, Int y )
{
	if (x >= m_extent.lo.x && x <= m_extent.hi.x &&
		y >= m_extent.lo.y && y <= m_extent.hi.y)
	{
		PathfindCell *cell = nullptr;
		if (layer > LAYER_GROUND && layer <= LAYER_LAST)
		{
			cell = m_layers[layer].getCell(x, y);
		}
  if (!cell) cell = &m_map[x][y];
#ifdef GENERALS_ZH_PARALLEL_PATH_BATCH
  if (auto* context=SearchContextBinding<PathfindSearchContext>::current())
   if (context->m_parallelReads && !context->m_occupancyQueryReads) observeParallelCell(cell);
#endif
  return cell;
	}
	else
	{
		return nullptr;
	}
}

inline PathfindCell *Pathfinder::getCell( PathfindLayerEnum layer, const Coord3D *pos )
{
	ICoord2D cell;
	Bool overflow = worldToCell( pos, &cell );
	if (overflow) return nullptr;
	return getCell( layer, cell.x, cell.y );
}

inline PathfindCell *Pathfinder::getClippedCell( PathfindLayerEnum layer, const Coord3D *pos)
{
	ICoord2D cell;
	worldToCell( pos, &cell );
	return getCell( layer, cell.x, cell.y );
}

inline Bool Pathfinder::worldToCell( const Coord3D *pos, ICoord2D *cell )
{
	cell->x = REAL_TO_INT_FLOOR(pos->x/PATHFIND_CELL_SIZE);
	cell->y = REAL_TO_INT_FLOOR(pos->y/PATHFIND_CELL_SIZE);
	Bool overflow = false;
	if (cell->x < m_extent.lo.x) {overflow = true; cell->x = m_extent.lo.x;}
	if (cell->y < m_extent.lo.y) {overflow = true; cell->y = m_extent.lo.y;}
	if (cell->x > m_extent.hi.x) {overflow = true; cell->x = m_extent.hi.x;}
	if (cell->y > m_extent.hi.y) {overflow = true; cell->y = m_extent.hi.y;}
	return overflow;
}

