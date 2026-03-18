# UCS Optimization Report

This document summarizes the current Uniform-Cost Search (UCS) implementation and the optimization strategy used in this project.

## Scope

This report covers only UCS-related implementation:

- `backend/solver/ucs/ucs.py`
- `backend/solver/ucs/ucs_utils.py`
- `backend/solver/ucs/ucs_profile.py`
- `backend/solver/ucs/__init__.py`

No BFS, DFS, or A* logic is modified by this report.

## Current UCS Architecture

### 1) Compact Search Node Representation

UCS uses compact frontier entries and arena-based metadata rather than storing full node objects in the heap.

- Frontier entry: `(cost, bias, counter, state_id)`
- Parent/edge chain arenas:
  - `parent_index_arena: list[int]`
  - `edge_move_ids_arena: list[tuple[int, ...]]`
  - `state_id_arena: list[int]`
  - `best_node_index[state_id] -> arena_index`

### 2) Move Interning (Compact Move Encoding)

Moves are interned and referenced by integer IDs.

- `move_pool[move_id] -> Move`
- `encode_edge_moves(...)` / `decode_edge_moves(...)`

This approach reduces duplicated move-object memory in large search trees.

### 3) Duplicate Detection + Cost Pruning

Canonical cost map:

- `best_cost[state_id] = best_g`

Dominance rule:

- Skip successor if `new_cost >= best_cost[next_state_id]`.

### 4) State Object Cache Separation

`State` objects are stored in `state_cache` only while they remain relevant for expansion, instead of being embedded directly in heap nodes.

### 5) Optional Bloom Pre-Filter

`BloomFilter` is available and mode-configurable (`ENABLE_BLOOM`) to pre-prune likely duplicates in speed-oriented profiles.

## Runtime Modes (Canonical)

UCS now supports three canonical backend modes:

- `first`
- `speed`
- `memory`

Any other mode string is rejected.

## Per-Mode Optimization Policy

Mode policies are defined in `UCS_MODE_PROFILES` (in `ucs_profile.py`) and generated from machine-dependent limits (CPU/RAM-aware baseline).

### `first` (first-solution fast)

Goal: return a valid solution as early as possible.

Typical behavior:

- Aggressive pruning and bounded expansion
- Returns immediately at first found goal (`RETURN_FIRST_GOAL=True`)
- Uses incumbent goal bound, truncation, compaction, and optional Bloom
- Fallback chain enabled

### `speed` (speed + cost focus)

Goal: maximize throughput while preserving better cost quality than `first`.

Typical behavior:

- Still speed-oriented (batching, optional truncation/compaction)
- May continue improving incumbent quality instead of immediate return
- Uses incumbent cost bound
- Fallback to memory-safe exact mode if needed

### `memory` (exact memory mode)

Goal: correctness-focused behavior with memory-safe settings.

Typical behavior:

- No approximate pruning (no Bloom, no partial expansion)
- Batch size = 1
- Frontier truncation disabled
- Returns on first goal pop (UCS property under nonnegative edge costs)

## Fallback Strategy

Fallback is mode-defined in `FALLBACK_MODES` and currently configured as:

- `first -> speed -> memory`
- `speed -> memory`
- `memory -> (none)`

If a mode run returns `None`, UCS automatically retries in the next fallback mode.

## Priority Queue and Expansion Behavior

### Priority Queue Ordering

The primary key remains UCS path cost (`g`), with deterministic tie-breaking:

1. `cost`
2. progress bias (`_priority_bias`)
3. insertion counter
4. `state_id`

This preserves UCS ordering by cost while improving plateau traversal behavior.

### Batch Expansion

Nodes that share the same minimum cost can be expanded in mode-configured batches (`BATCH_EXPANSION_SIZE`) to reduce overhead.

### Partial Expansion and Move Cap (Mode-Configurable)

- `MAX_MOVES_PER_STATE`
- `PARTIAL_EXPANSION_WIDTH`

These controls are applied only when enabled by the active mode profile.

## Compaction and Truncation

### Frontier Truncation

When enabled per mode and threshold reached:

- Keep only best `KEEP_FRONTIER` heap entries.

### Arena Compaction

`compact_ucs_structures(...)` prunes arena metadata to frontier-relevant ancestors.

Inputs include mode-specific keep size and the current frontier anchor.

## Runtime Progress Logging

When `UCS_RUNTIME_LOG_ENABLED` is `true`, UCS prints periodic runtime progress:

- `mode`
- elapsed time (`t`)
- `frontier`
- `visited`
- `expanded`
- `expanded/s` (window throughput)

Log interval is controlled by `UCS_RUNTIME_LOG_INTERVAL_SECONDS`.

## Validation

Validation snapshot command:

```bash
python -m pytest tests/test_ucs.py -q
```

Result:

- `5 passed`

## Notes

- This report reflects the current implementation state (mode-based profiles + fallback strategy).
- Earlier experimental features (e.g., fixed anytime timeout cap) are no longer part of the active design.
