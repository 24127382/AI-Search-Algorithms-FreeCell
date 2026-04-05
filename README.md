# AI Search Algorithms FreeCell

Desktop FreeCell app with AI solvers (BFS, DFS, UCS, A*) built on PySide6.

## Overview

This repository contains a complete FreeCell desktop application plus a search
engine used to solve game states with classical AI algorithms.

Main goals of this project:

- Provide a playable FreeCell UI (Qt/PySide6).
- Compare multiple search strategies on the same domain model.
- Keep solver internals measurable via runtime stats.
- Support deterministic Microsoft-style deals for reproducible experiments.

## Features

- Play FreeCell manually (drag/drop, click move, undo, restart).
- Start from a specific deal number or random deal.
- Auto-foundation helper for safe progress.
- Run solver in background thread without freezing UI.
- Stop solver at any time.
- Review solver result step-by-step:
	- previous/next move
	- play/pause playback
	- open full move list and jump to any step
- Runtime stats for BFS/DFS/UCS/A* runs.
- Benchmarks for packed state key vs unpacked state key.

## Tech Stack

- Python >= 3.13
- PySide6 (desktop UI)
- pytest (tests)
- pandas/matplotlib/numpy (experiments/benchmarking support)
- freecell-solver (dependency in project metadata)

## Project Structure

```text
.
|- main.py                      # Root entrypoint
|- pyproject.toml               # Project metadata + dependencies
|- requirements.txt             # Pip-friendly dependency list
|- asset/                       # Card/sound assets
|- source/
|  |- app/                      # Application entrypoint wiring
|  |- application/
|  |  |- engine/                # Move generation, move application, deal/shuffle
|  |  |- services/              # GameService/SolverService facades for UI
|  |  \- experiments/           # Benchmarks and solver stats formatting
|  |- domain/
|  |  |- model/                 # Card, Move, State (immutable/canonical key)
|  |  |- rule/                  # FreeCell rule checks
|  |  \- solver/
|  |     |- bfs.py dfs.py ucs.py astar.py
|  |     |- algorithms.py       # Search facade + supported keys
|  |     |- search_utils/       # Profiles + UCS/A* helpers
|  |     \- utils/              # Heuristics, env parsing, state helpers
|  \- presentation/
|     \- qt/
|        |- main_window.py control_panel.py
|        |- board/              # Board widget + move/solver mixins + thread
|        |- card/               # Qt card assets/helpers
|        \- shared/             # Qt/env helpers
|- tests/                       # Regression/stat tests + benchmark script
\- benchmark_results/           # Generated experiment outputs
```

## Architecture

The codebase follows a layered design:

- `presentation`:
	- Qt widgets and user interaction.
	- Never directly manipulates low-level rule internals.
- `application`:
	- Orchestrates engine and services for UI.
	- Owns state transition entrypoints exposed to presentation.
- `domain`:
	- Core game model (`State`, `Move`, `Card`).
	- Rule validation and solver implementations.

This separation makes it easier to:

- run solvers outside UI,
- test domain logic independently,
- tune algorithms without rewriting frontend code.

## Setup

### Prerequisites

- Python `>= 3.13`
- `uv` (recommended) or `pip`
- Git

### 1. Clone repository

```bash
git clone https://github.com/<your-org>/AI-Search-Algorithms-FreeCell.git
cd AI-Search-Algorithms-FreeCell
```

### 2. Create environment and install dependencies

Option A - using `uv` (recommended):

```bash
uv sync
```

Option B - using `pip` + virtual environment:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Verify setup

```bash
uv run pytest -q
```

If all tests pass, setup is complete and you can run the app.

## Run Application

```bash
uv run main.py
```

Alternative script entrypoint (defined in `pyproject.toml`):

```bash
uv run freecell-app
```

When app starts:

- You can enter a deal number (integer) for deterministic setup.
- Leave blank to use random deal.

## Controls in UI

- `New Game`: open deal dialog and start a new deal.
- `Restart`: reset current deal to initial state.
- `Undo`: revert one move.
- `Solver`: choose one of `BFS`, `DFS`, `UCS`, `A*`.
- `Auto Foundation`: apply first legal move to foundation.
- `Stop`: stop running solver/replay.

After solver finds a path, review mode is enabled:

- `List of move` dialog for direct jump.
- `Previous`/`Next` buttons.
- `Play/Pause` timed playback.

## Solver Algorithms

### BFS

- Breadth-first traversal.
- Uses canonical state key deduplication.
- Stops on cancellation, hard time cap, or expanded-node limit.
- Returns shortest solution in number of moves (when solution exists).

### DFS

- Plain depth-first traversal.
- Uses visited-state deduplication.
- Stops when solved, exhausted, cancelled, or hard time cap is reached.

### UCS

- Uniform-Cost Search on weighted move costs.
- Uses dominance pruning based on best-known `g` cost per state.
- Uses forced safe-foundation closure after each expanded move.
- Shares cost model with A* to make comparisons meaningful.

### A* (Weighted)

- Weighted A*: `f(n) = g(n) + w * h(n)`.
- `g` uses same edge cost function as UCS.
- Default heuristic weight from `ASTAR_WEIGHT` (default `5.0`).
- Default heuristic in app facade is `buried_cards`.
- Reopen policy for better paths when needed.

## Heuristics and Cost Model

Implemented heuristics include:

- `zero_heuristic`
- `cards_remaining_heuristic`
- `foundation_distance`
- `buried_cards`
- `combined_heuristic = max(foundation_distance, buried_cards)`
- `progress_pressure_heuristic` (aggressive, may be inadmissible)
- `foundation_cost_lower_bound` (cost-aware lower bound for negative foundation cost)

Cost model (`ucs_move_cost`) rewards/penalizes structural effects such as:

- foundation progress,
- creating empty tableau columns,
- breaking existing stacks,
- unnecessary empty-column fills,
- freecell usage patterns.

## State Representation and Performance Notes

- `State` is immutable.
- Canonical board identity uses cached `board_code`.
- Equality/hash are optimized around this canonical encoding.
- Move generation includes optional canonical redundancy pruning.
- Forced safe-foundation closure is available for algorithms that use collapsed edges.

This design reduces duplicate-state explosion and supports faster solver loops.

## Tests

Run all tests:

```bash
uv run pytest -q
```

Current test coverage focuses on:

- solver regression checks,
- cancellation behavior,
- stat formatting and compatibility fields,
- move pruning behavior.

## Benchmark (Packed vs Unpacked State Keys)

Benchmark script:

- `tests/benchmark_state_packing.py`

Example run:

```bash
uv run python tests/benchmark_state_packing.py --deal 1 --max-expand 100000 --trials 5
```

This benchmark compares runtime/memory when using:

- packed canonical key (`state.board_code`)
- unpacked tuple key (`tableau`, `freecells`, `foundations`)

Solver tuning benchmark script:

- `source/application/experiments/benchmark_ucs_astar_tuning.py`

## Environment Variables

Below are tunable environment variables discovered from the source code.

### Solver Runtime Logs

| Variable | Default | Description |
|---|---:|---|
| `BFS_RUNTIME_LOG` | `1` | Print BFS runtime stats (`0` to disable). |
| `DFS_RUNTIME_LOG` | `1` | Print DFS runtime stats (`0` to disable). |
| `UCS_RUNTIME_LOG` | `1` | Print UCS runtime stats (`0` to disable). |
| `ASTAR_RUNTIME_LOG` | `1` | Print A* runtime stats (`0` to disable). |

### Search Loop Intervals

| Variable | Default | Description |
|---|---:|---|
| `BFS_INNER_CANCEL_CHECK_INTERVAL` | `256` | Cancel check frequency inside BFS move loop. |
| `DFS_INNER_CANCEL_CHECK_INTERVAL` | `256` | Cancel check frequency inside DFS move loop. |
| `UCS_INNER_CANCEL_CHECK_INTERVAL` | `256` | Cancel check frequency inside UCS move loop. |
| `ASTAR_INNER_CANCEL_CHECK_INTERVAL` | `256` | Cancel check frequency inside A* move loop. |
| `BFS_STATS_UPDATE_INTERVAL` | `32` | Peak-stat refresh frequency for BFS. |
| `DFS_STATS_UPDATE_INTERVAL` | `32` | Peak-stat refresh frequency for DFS. |
| `UCS_STATS_UPDATE_INTERVAL` | `32` | Peak-stat refresh frequency for UCS. |
| `ASTAR_STATS_UPDATE_INTERVAL` | `32` | Peak-stat refresh frequency for A*. |

### BFS and DFS Limits

| Variable | Default |
|---|---:|
| `BFS_HARD_TIME_CAP_MS` | `60000.0` |
| `BFS_MAX_EXPANDED_NODES` | `1000000` |
| `DFS_HARD_TIME_CAP_MS` | `60000.0` |

### A* Arena/Compaction

| Variable | Default | Description |
|---|---:|---|
| `ASTAR_COMPACT_MIN_ARENA_NODES` | `4096` | Periodic threshold for compaction checks. |
| `ASTAR_COMPACT_ARENA_LIVE_RATIO` | `2` | Compaction aggressiveness ratio. |

### UCS Search Profile

| Variable | Default | Description |
|---|---:|---|
| `UCS_SORT_CANDIDATE_MOVES` | `False` | Deterministic candidate sorting before expansion. |
| `UCS_PRUNE_SAFE_MOVES` | `True` | Collapse safe-foundation branch to one dominant move. |
| `UCS_PRUNE_IMMEDIATE_UNDO` | `True` | Skip direct one-step undo moves. |
| `UCS_PRUNE_CANONICAL_REDUNDANT` | `True` | Prune canonical-equivalent move variants. |
| `UCS_DOMINANCE_PRUNING_ENABLED` | `True` | Enable best-cost dominance pruning. |
| `UCS_MOVE_INTERNING_ENABLED` | `True` | Intern move signatures to reduce memory. |

### A* and Search Tie-Break Bias

| Variable | Default |
|---|---:|
| `ASTAR_WEIGHT` | `5.0` |
| `SEARCH_PRIORITY_FOUNDATION_WEIGHT` | `16` |
| `SEARCH_PRIORITY_EMPTY_TABLEAU_WEIGHT` | `3` |
| `SEARCH_PRIORITY_OCCUPIED_FREECELL_PENALTY` | `1` |

### UCS Cost Model

| Variable | Default |
|---|---:|
| `UCS_MEANINGLESS_FILL_MAX_SEQUENCE_LEN` | `3` |
| `UCS_MEANINGLESS_FILL_MIN_REMAINING_LEN` | `1` |
| `UCS_FOUNDATION_MOVE_COST` | `-19` |
| `UCS_BASE_MOVE_COST` | `6` |
| `UCS_GOOD_TABLEAU_BUILD_BONUS` | `2` |
| `UCS_CREATE_EMPTY_COLUMN_BONUS` | `2` |
| `UCS_BREAK_STACK_PENALTY` | `3` |
| `UCS_MEANINGLESS_EMPTY_FILL_PENALTY` | `3` |
| `UCS_RESTRUCTURE_PENALTY_CAP` | `9` |
| `UCS_TO_FREECELL_PENALTY` | `2` |
| `UCS_FROM_FREECELL_TO_TABLEAU_BONUS` | `1` |
| `UCS_FOUNDATION_PROGRESS_COST_CAP` | `1` |
| `UCS_MIN_EDGE_COST` | `1` |

### Frontend / UX

| Variable | Default | Description |
|---|---:|---|
| `FRONTEND_SOLVER_ALGORITHMS` | `BFS,DFS,UCS,A*` | Solver options shown in menu. |
| `FRONTEND_SOLVER_PLAYBACK_INTERVAL_MS` | `300` | Replay interval in review mode. |
| `FRONTEND_SOLVER_MOVE_LIST_DIALOG_WIDTH` | `540` | Move-list dialog width. |
| `FRONTEND_SOLVER_MOVE_LIST_DIALOG_HEIGHT` | `420` | Move-list dialog height. |
| `FRONTEND_SOLVER_THREAD_STOP_TIMEOUT_MS` | `250` | Graceful thread-stop wait time. |
| `FRONTEND_SOLVER_THREAD_FORCE_WAIT_MS` | `500` | Extra wait before force termination path. |

## Development Notes

- Primary entrypoint: `main.py` -> `source.app.main:main`.
- Solver facade for UI: `source.application.services.solver_service`.
- Game state/build service: `source.application.services.game_service`.
- Supported solver keys: `BFS`, `DFS`, `UCS`, `A*`.

## Packaging

`pyproject.toml` defines:

- package name: `ai-search-algorithms-freecell`
- script: `freecell-app = source.app.main:main`
- source package: `source`

## Quick Commands

```bash
# Install deps
uv sync

# Run app
uv run main.py

# Run tests
uv run pytest -q

```
