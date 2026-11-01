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
