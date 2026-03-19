"""Runtime profile presets that tune UCS for host machine resources."""

import os
import platform
import ctypes


def _total_ram_gb() -> float:
	"""Detect total physical RAM in gigabytes.

	Returns:
		float: Total RAM in GB, or `0.0` when unavailable.
	"""
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
	"""Select machine-dependent runtime limits.

	Returns:
		dict: Limit profile with frontier/visited/bloom settings.
	"""
	cpu_count = os.cpu_count() or 4
	ram_gb = _total_ram_gb()

	if ram_gb and ram_gb <= 8:
		return {
			"MAX_VISITED": 1_200_000,
			"MAX_FRONTIER": 800_000,
			"KEEP_FRONTIER": 500_000,
			"COMPACTION_GAP": 300_000,
			"BLOOM_BITS": 24_000_000,
			"BLOOM_HASH_COUNT": 3,
		}

	if ram_gb and ram_gb <= 16:
		return {
			"MAX_VISITED": 3_500_000,
			"MAX_FRONTIER": 2_000_000,
			"KEEP_FRONTIER": 1_200_000,
			"COMPACTION_GAP": 700_000,
			"BLOOM_BITS": 48_000_000,
			"BLOOM_HASH_COUNT": 4,
		}

	if cpu_count >= 12:
		return {
			"MAX_VISITED": 16_000_000,
			"MAX_FRONTIER": 8_000_000,
			"KEEP_FRONTIER": 4_500_000,
			"COMPACTION_GAP": 2_000_000,
			"BLOOM_BITS": 120_000_000,
			"BLOOM_HASH_COUNT": 6,
		}

	if cpu_count >= 8:
		return {
			"MAX_VISITED": 12_000_000,
			"MAX_FRONTIER": 6_000_000,
			"KEEP_FRONTIER": 3_500_000,
			"COMPACTION_GAP": 1_500_000,
			"BLOOM_BITS": 96_000_000,
			"BLOOM_HASH_COUNT": 5,
		}

	return {
		"MAX_VISITED": 6_000_000,
		"MAX_FRONTIER": 3_000_000,
		"KEEP_FRONTIER": 1_800_000,
		"COMPACTION_GAP": 900_000,
		"BLOOM_BITS": 64_000_000,
		"BLOOM_HASH_COUNT": 4,
	}


def _build_mode_profiles(limits: dict) -> dict:
	"""Build mode-specific UCS config maps from machine limits.

	Args:
		limits: Machine-dependent hard limits.

	Returns:
		dict: UCS mode profile dictionary.
	"""
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
			"ENABLE_ANTI_CYCLE": True,
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
			"ENABLE_ANTI_CYCLE": True,
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
			"ENABLE_ANTI_CYCLE": False,
		},
	}


UCS_MODE_PROFILES = _build_mode_profiles(_machine_limits())
UCS_RUNTIME_LOG_ENABLED = os.environ.get("UCS_RUNTIME_LOG", "1") != "0"
UCS_RUNTIME_LOG_INTERVAL_SECONDS = float(os.environ.get("UCS_RUNTIME_LOG_INTERVAL", "10.0"))
