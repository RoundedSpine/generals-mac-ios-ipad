#pragma once

#include "Common/MemoryPoolUsage.h"
#include <cstdio>
#include <cstring>

// GeneralsX @feature Codex 01/11/2026 Keep only the preceding named pool snapshot and bounded rankings, with no heap allocations or per-frame work.
namespace gxpoolmemory {
class Tracker
{
public:
	static constexpr size_t Capacity = 1024;
	static constexpr size_t GrowthRows = 8;
	static constexpr size_t ResidentRows = 4;

	MemoryPoolUsage* entries() { return m_samples[m_current]; }
	void reset() { m_previousCount = 0; m_hasPrevious = false; }

	// Called after the factory has released its lock, on the main sampling thread.
	void log(FILE* output, size_t total)
	{
		const size_t count = total < Capacity ? total : Capacity;
		const MemoryPoolUsage* current = m_samples[m_current];
		const MemoryPoolUsage* previous = m_samples[1 - m_current];
		Change changes[Capacity];
		Rank growth[GrowthRows] = {}, live[ResidentRows] = {}, reserved[ResidentRows] = {};
		size_t growing = 0, newlySeen = 0;
		for (size_t i = 0; i < count; ++i) {
			const MemoryPoolUsage& pool = current[i];
			const MemoryPoolUsage* old = nullptr;
			for (size_t j = 0; j < m_previousCount; ++j) {
				if (pool.identity == previous[j].identity && pool.allocationSize == previous[j].allocationSize &&
					std::strcmp(pool.name, previous[j].name) == 0) {
					old = &previous[j];
					break;
				}
			}
			const size_t used = pool.usedBlocks * pool.allocationSize;
			const size_t allocated = pool.totalBlocks * pool.allocationSize;
			Change& change = changes[i];
			change.baseline = !m_hasPrevious ? "first_sample" : old ? "previous_sample" : "not_in_previous";
			change.used = m_hasPrevious ? difference(used, old ? old->usedBlocks * old->allocationSize : 0) : 0;
			change.reserved = m_hasPrevious ? difference(allocated, old ? old->totalBlocks * old->allocationSize : 0) : 0;
			change.blocks = m_hasPrevious ? difference(pool.usedBlocks, old ? old->usedBlocks : 0) : 0;
			if (!old) ++newlySeen;
			if (change.used > 0) {
				++growing;
				insert(growth, GrowthRows, i, static_cast<size_t>(change.used));
			}
			if (used) insert(live, ResidentRows, i, used);
			if (allocated) insert(reserved, ResidentRows, i, allocated);
		}
		size_t rows = 0;
		for (size_t i = 0; i < count; ++i)
			if (rankOf(growth, GrowthRows, i) || rankOf(live, ResidentRows, i) || rankOf(reserved, ResidentRows, i)) ++rows;
		std::fprintf(output, "[IOS_MEMORY_POOLS] total=%zu captured=%zu omitted=%zu previous_captured=%zu growing_used=%zu newly_seen=%zu rows=%zu tracker_bytes=%zu coverage=engine_pool_payload\n",
			total, count, total - count, m_previousCount, growing, newlySeen, rows, sizeof(*this));
		for (size_t i = 0; i < count; ++i) {
			const size_t growthRank = rankOf(growth, GrowthRows, i);
			const size_t liveRank = rankOf(live, ResidentRows, i);
			const size_t reservedRank = rankOf(reserved, ResidentRows, i);
			if (!growthRank && !liveRank && !reservedRank) continue;
			const MemoryPoolUsage& pool = current[i];
			char label[sizeof(pool.name)];
			for (size_t n = 0; n < sizeof(label); ++n) {
				const unsigned char ch = static_cast<unsigned char>(pool.name[n]);
				label[n] = ch <= 32 || ch == '"' || ch == '\\' || ch == 127 ? '_' : ch;
				if (!ch) { label[n] = '\0'; break; }
			}
			label[sizeof(label) - 1] = '\0';
			std::fprintf(output, "[IOS_MEMORY_POOL] name=\"%s\" name_truncated=%d block_bytes=%zu live_blocks=%zu reserved_blocks=%zu used_bytes=%zu reserved_bytes=%zu used_delta_bytes=%lld reserved_delta_bytes=%lld live_delta_blocks=%lld baseline=%s growth_rank=%zu live_rank=%zu reserved_rank=%zu\n",
				label, pool.nameTruncated ? 1 : 0, pool.allocationSize, pool.usedBlocks, pool.totalBlocks,
				pool.usedBlocks * pool.allocationSize, pool.totalBlocks * pool.allocationSize,
				changes[i].used, changes[i].reserved, changes[i].blocks, changes[i].baseline, growthRank, liveRank, reservedRank);
		}
		m_previousCount = count;
		m_hasPrevious = true;
		m_current = 1 - m_current;
	}

private:
	struct Change { long long used, reserved, blocks; const char* baseline; };
	struct Rank { size_t index, bytes; };
	static long long difference(size_t now, size_t before)
	{
		return now >= before ? static_cast<long long>(now - before) : -static_cast<long long>(before - now);
	}
	void insert(Rank* ranks, size_t count, size_t index, size_t bytes) const
	{
		for (size_t at = 0; at < count; ++at) {
			if (bytes > ranks[at].bytes || (bytes == ranks[at].bytes &&
				std::strcmp(m_samples[m_current][index].name, m_samples[m_current][ranks[at].index].name) < 0)) {
				for (size_t j = count - 1; j > at; --j) ranks[j] = ranks[j - 1];
				ranks[at] = {index, bytes};
				break;
			}
		}
	}
	static size_t rankOf(const Rank* ranks, size_t count, size_t index)
	{
		for (size_t i = 0; i < count; ++i)
			if (ranks[i].bytes && ranks[i].index == index) return i + 1;
		return 0;
	}
	MemoryPoolUsage m_samples[2][Capacity];
	size_t m_current = 0;
	size_t m_previousCount = 0;
	bool m_hasPrevious = false;
};
}
