#pragma once

#include <stddef.h>

// GeneralsX @feature Codex 01/11/2026 Copy names and payload counters while locked; pool identity is never dereferenced by diagnostics.
struct MemoryPoolUsage
{
	const void* identity; // Opaque comparison key only; never dereference after the snapshot.
	char name[96];
	size_t allocationSize;
	size_t usedBlocks;
	size_t totalBlocks;
	bool nameTruncated;
};

// GeneralsX @feature Codex 01/11/2026 Native providers measure base system allocations, including engine headers and native size-class rounding.
typedef size_t (*MemoryAllocationSizeQuery)(const void*);
struct RawMemoryUsage
{
	size_t allocators;
	size_t liveBlocks;
	size_t allocatedBytes;
	size_t largestBlock;
	size_t unmeasuredBlocks;
	size_t sizeBuckets[6]; // Disjoint ranges: (0,4 KiB], (4,16 KiB], (16,64 KiB], (64,256 KiB], (256 KiB,1 MiB], >1 MiB.
};
