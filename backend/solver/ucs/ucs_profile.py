import os
import platform
import ctypes


def _total_ram_gb() -> float:
	try:
		if platform.system() == "Windows":
			class MEMORYSTATUSEX(ctypes.Structure):
				_fields_ = [
					("dwLength", ctypes.c_ulong),
					("dwMemoryLoad", ctypes.c_ulong),
					("ullTotalPhys", ctypes.c_ulonglong),
					("ullAvailPhys", ctypes.c_ulonglong),
					("ullTotalPageFile", ctypes.c_ulonglong),
					("ullAvailPageFile", ctypes.c_ulonglong),
					("ullTotalVirtual", ctypes.c_ulonglong),
					("ullAvailVirtual", ctypes.c_ulonglong),
					("sullAvailExtendedVirtual", ctypes.c_ulonglong),
				]

			status = MEMORYSTATUSEX()
			status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
			if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
				return status.ullTotalPhys / (1024 ** 3)

		if hasattr(os, "sysconf"):
			pages = os.sysconf("SC_PHYS_PAGES")
			page_size = os.sysconf("SC_PAGE_SIZE")
			return (pages * page_size) / (1024 ** 3)
	except Exception:
		return 0.0

	return 0.0


def _machine_limits() -> dict:
	cpu_count = os.cpu_count() or 4
	ram_gb = _total_ram_gb()

	if ram_gb and ram_gb <= 8:
		return {
			"MAX_VISITED": 180000,
			"MAX_FRONTIER": 250000,
			"KEEP_FRONTIER": 120000,
			"COMPACTION_GAP": 70000,
			"BLOOM_BITS": 6_000_000,
			"BLOOM_HASH_COUNT": 3,
		}

	if ram_gb and ram_gb <= 16:
		return {
			"MAX_VISITED": 350000,
			"MAX_FRONTIER": 500000,
			"KEEP_FRONTIER": 240000,
			"COMPACTION_GAP": 120000,
			"BLOOM_BITS": 12_000_000,
			"BLOOM_HASH_COUNT": 4,
		}

	if cpu_count >= 12:
		return {
			"MAX_VISITED": 700000,
			"MAX_FRONTIER": 1_000_000,
			"KEEP_FRONTIER": 420000,
			"COMPACTION_GAP": 240000,
			"BLOOM_BITS": 24_000_000,
			"BLOOM_HASH_COUNT": 5,
		}

	if cpu_count >= 8:
		return {
			"MAX_VISITED": 500000,
			"MAX_FRONTIER": 720000,
			"KEEP_FRONTIER": 320000,
			"COMPACTION_GAP": 180000,
			"BLOOM_BITS": 18_000_000,
			"BLOOM_HASH_COUNT": 4,
		}

	return {
		"MAX_VISITED": 260000,
		"MAX_FRONTIER": 360000,
		"KEEP_FRONTIER": 170000,
		"COMPACTION_GAP": 100000,
		"BLOOM_BITS": 10_000_000,
		"BLOOM_HASH_COUNT": 4,
	}


def _build_mode_profiles(limits: dict) -> dict:
	max_visited = limits["MAX_VISITED"]
	max_frontier = limits["MAX_FRONTIER"]
	keep_frontier = limits["KEEP_FRONTIER"]
	compaction_gap = limits["COMPACTION_GAP"]
	bloom_bits = limits["BLOOM_BITS"]
	bloom_hash_count = limits["BLOOM_HASH_COUNT"]

	return {
		"first": {
			"MAX_VISITED": max_visited,
			"MAX_FRONTIER": max_frontier,
			"KEEP_FRONTIER": keep_frontier,
			"COMPACTION_GAP": compaction_gap,
			"MAX_MOVES_PER_STATE": 10,
			"BATCH_EXPANSION_SIZE": 14,
			"PARTIAL_EXPANSION_WIDTH": 8,
			"EARLY_GOAL_BOUNDING": True,
			"ENABLE_BLOOM": True,
			"BLOOM_BITS": bloom_bits,
			"BLOOM_HASH_COUNT": bloom_hash_count,
			"ENABLE_FRONTIER_TRUNCATION": True,
			"ENABLE_ARENA_COMPACTION": True,
			"RETURN_FIRST_GOAL": True,
			"USE_INCUMBENT_COST_BOUND": True,
			"FALLBACK_MODES": ("speed", "memory"),
		},
		"speed": {
			"MAX_VISITED": max_visited,
			"MAX_FRONTIER": max_frontier,
			"KEEP_FRONTIER": keep_frontier,
			"COMPACTION_GAP": compaction_gap,
			"MAX_MOVES_PER_STATE": 14,
			"BATCH_EXPANSION_SIZE": 10,
			"PARTIAL_EXPANSION_WIDTH": 12,
			"EARLY_GOAL_BOUNDING": True,
			"ENABLE_BLOOM": False,
			"BLOOM_BITS": bloom_bits,
			"BLOOM_HASH_COUNT": bloom_hash_count,
			"ENABLE_FRONTIER_TRUNCATION": True,
			"ENABLE_ARENA_COMPACTION": True,
			"RETURN_FIRST_GOAL": False,
			"USE_INCUMBENT_COST_BOUND": True,
			"FALLBACK_MODES": ("memory",),
		},
		"memory": {
			"MAX_VISITED": int(max_visited * 2.0),
			"MAX_FRONTIER": int(max_frontier * 2.0),
			"KEEP_FRONTIER": int(max_frontier * 2.0),
			"COMPACTION_GAP": int(compaction_gap * 1.5),
			"MAX_MOVES_PER_STATE": 0,
			"BATCH_EXPANSION_SIZE": 1,
			"PARTIAL_EXPANSION_WIDTH": 0,
			"EARLY_GOAL_BOUNDING": False,
			"ENABLE_BLOOM": False,
			"BLOOM_BITS": bloom_bits,
			"BLOOM_HASH_COUNT": bloom_hash_count,
			"ENABLE_FRONTIER_TRUNCATION": False,
			"ENABLE_ARENA_COMPACTION": True,
			"RETURN_FIRST_GOAL": True,
			"USE_INCUMBENT_COST_BOUND": False,
			"FALLBACK_MODES": (),
		},
	}


UCS_MODE_PROFILES = _build_mode_profiles(_machine_limits())
UCS_RUNTIME_LOG_ENABLED = os.environ.get("UCS_RUNTIME_LOG", "1") != "0"
UCS_RUNTIME_LOG_INTERVAL_SECONDS = float(os.environ.get("UCS_RUNTIME_LOG_INTERVAL", "1.0"))
