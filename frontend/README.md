# Frontend Architecture Guide

This document describes the frontend layer of the FreeCell application, including UI composition, user interaction flow, rendering behavior, and integration with backend search logic.

## 1) Frontend Responsibilities

The frontend is responsible for:

- Building and styling the Qt UI (window, board, controls, cards).
- Translating user actions (click, double-click, drag/drop) into board moves.
- Maintaining UI-level session state (selection, move count, status messages).
- Running solver operations asynchronously and replaying resulting move sequences.
- Emitting user feedback (`status_changed`, move count updates, win notifications).

The frontend does **not** implement game rules directly. Legal move generation and state transitions are delegated to backend modules.

---

## 2) High-Level Module Structure

- `main_window.py`
  - App entry UI.
  - Difficulty dialog.
  - Main window composition (`ControlPanel` + `BoardWidget`).
- `control_panel.py`
  - Action buttons and solver menu.
  - Emits UI commands via Qt signals.

### `board/`
- `widget.py`
  - Concrete board widget that composes all board mixins.
  - Owns core board state and lifecycle (`new_game`, difficulty, history).
- `constants.py`
  - Slot type constants and difficulty constants.
- `slot_widgets.py`
  - Slot-level draggable/droppable widgets.
- `dragdrop.py`
  - Parsing helper for slot drag payloads.
- `move_core_mixin.py`
  - Core move resolution and application workflow.
- `move_interaction_mixin.py`
  - Click/double-click behavior and source selection logic.
- `solver_mixin.py`
  - Undo/restart/auto-foundation and solver orchestration.
- `solver_thread.py`
  - Background worker thread for solver execution.
- `ui_layout_mixin.py`
  - Board layout and widget wiring.
- `ui_render_mixin.py`
  - Rendering pipeline from backend `State` to visible widgets.

### `card/`
- `widget.py`
  - Card UI element with custom painting and drag/drop behavior.
- `paint.py`
  - Card face and overlay painting primitives.
- `drag.py`
  - Drag payload and drag preview pixmap helpers.
- `assets.py`
  - Suit symbols and card asset path lookup.

### `shared/`
- `qt.py`
  - Compatibility layer for `PySide6` / `PyQt6`.
- `animation.py`
  - Reusable fade/move animations.
- `__init__.py`
  - Shared exports.

---

## 3) UI Composition and Ownership

## MainWindow

`MainWindow` owns two main child widgets:

1. `ControlPanel` (top action bar)
2. `BoardWidget` (play area)

Signals from `ControlPanel` are connected to methods on `BoardWidget`.
Signals from `BoardWidget` are connected back to `MainWindow` status bar and victory dialog.

## BoardWidget

`BoardWidget` is the main integration object and state owner for gameplay UI.

Important attributes:

- `state`: current immutable backend `State`.
- `initial_state`: snapshot used for restart.
- `history`: stack of previous states for undo.
- `selected_source`: currently selected source slot/card.
- `move_count`: UI move counter.
- `solver_thread`, `is_solving`, `_solve_started_at`: solver runtime control.
- Widget registries:
  - `_freecell_buttons`
  - `_foundation_buttons`
  - `_tableau_buttons`
  - `_tableau_layouts`
  - `_card_registry`

The mixin composition keeps responsibilities isolated while preserving one concrete widget class.

---

## 4) Runtime Flow

## Startup

1. `main()` launches `QApplication`.
2. `DifficultyDialog` collects selected difficulty.
3. `MainWindow` creates `BoardWidget(difficulty=...)`.
4. `BoardWidget.new_game()` initializes `State` and renders board.

## New Game

`BoardWidget.new_game()`:

- Builds initial state (`_build_initial_state`).
- Clears history and selection.
- Resets move counter.
- Calls `_render()`.
- Emits status message with difficulty and deal number.

## Move Execution (manual)

Typical path:

1. User clicks card/slot or performs drag/drop.
2. Interaction handler resolves source/target.
3. `BoardMoveCoreMixin._try_move()` finds candidate in backend `get_valid_moves(...)`.
4. If valid:
   - Current state is pushed to history.
   - New state is computed with backend `apply_move(...)`.
   - Move count and status are updated.
   - Goal state triggers win signal.
5. If invalid:
   - User sees rule-aware error message.

---

## 5) Signals and Event Wiring

## ControlPanel -> BoardWidget

- `new_game_requested` -> `new_game`
- `restart_requested` -> `restart`
- `undo_requested` -> `undo`
- `solve_requested(algo, mode)` -> `solve_with_algo`
- `auto_foundation_requested` -> `auto_to_foundation`

## BoardWidget -> MainWindow/ControlPanel

- `status_changed(str)` -> status bar text
- `move_count_changed(int)` -> move count label
- `game_won` -> victory dialog

---

## 6) Rendering Pipeline

Rendering is centralized in `BoardUiRenderMixin._render()`:

1. Disable widget updates temporarily for smoother batch updates.
2. Render freecells.
3. Render foundations.
4. Render tableau columns/cards.
5. Re-enable updates and emit move count.

Card widgets are reused via `_card_registry` to avoid unnecessary recreation and flicker.
If parent changes (e.g., moving from tableau to foundation), widget is reparented and animated.

Animations:

- `fade_in(widget)` for newly created cards.
- `animate_move(widget, start, end)` for transitions.

---

## 7) Drag-and-Drop Protocol

Payload format examples:

- `tableau:3` (column source)
- `tableau:3:5` (specific card index in column)
- `freecell:1`

Helpers:

- `board.dragdrop.parse_drag_payload(...)`
- `card.drag.parse_drop_position(...)`

Behavior highlights:

- Drag starts only after movement threshold to avoid accidental drags.
- Stacked drag pixmap is generated for multi-card tableau sequence drags.
- During drag, dragged widgets may be hidden then restored.

---

## 8) Solver Integration

`BoardSolverMixin.solve_with_algo(...)` starts a `SolverThread`.

Thread flow:

1. `SolverThread.run()` creates `SearchAlgorithm(state, mode=ucs_mode)`.
2. Calls `search(algo)`.
3. Emits either `result_ready(path)` or `error_occurred(message)`.

Main-thread handling:

- On success: starts a timer to replay moves step-by-step.
- On failure: updates status text.
- On finish: clears thread references.

Replay uses backend `apply_move(...)` for each move so replay state always stays rule-compliant.

---

## 9) Interaction Rules (Frontend Layer)

Frontend-specific behaviors include:

- Click-to-select source then click target.
- Double-click to auto-move to foundation; fallback to freecell when possible.
- Selection highlighting for source cards/columns.
- User-friendly status messages for invalid moves and sequence limits.

Rule legality always comes from backend move generation; frontend only coordinates UX.

---

## 10) Qt Compatibility Strategy

`shared/qt.py` abstracts Qt imports and exports one API surface.

- Tries `PySide6` first.
- Falls back to `PyQt6`.
- Exposes `QT_API` so UI can display active backend.

This allows the rest of frontend code to stay import-stable.

---

## 11) Extension Guidelines

If you add a new board interaction:

1. Add/extend signal in `ControlPanel` (if user-triggered).
2. Implement behavior in relevant mixin (`move_interaction`, `move_core`, or `solver_mixin`).
3. Keep legality checks delegated to backend (`get_valid_moves`, `apply_move`).
4. Emit clear status messages and update render state consistently.

If you add new visual effects:

- Prefer reusing `shared/animation.py`.
- Keep card painting logic in `card/paint.py`.
- Avoid duplicating animation objects without cleanup.

---

## 12) Debugging Checklist

If UI appears out of sync:

- Verify `_render()` is called after state changes.
- Verify `self.state` is replaced with a new backend state after move application.
- Ensure `selected_source` resets when move attempts complete.

If drag/drop fails:

- Check payload shape and parser behavior.
- Confirm target widget accepts drops.
- Confirm source is currently draggable.

If solver blocks UI:

- Confirm solving is done through `SolverThread`, not main thread.
- Confirm replay uses `QTimer` and small per-tick work.

---

## 13) Backend Contracts Used by Frontend

Frontend relies heavily on these backend contracts:

- `backend.model.state.State`
- `backend.engine.engine.get_valid_moves(...)`
- `backend.engine.engine.apply_move(...)`
- `backend.rule.rules.get_movable_sequences(...)`
- `backend.rule.rules.get_max_sequence_length(...)`
- `backend.solver.algorithms.SearchAlgorithm`

Any backend API signature changes should be coordinated with frontend mixins.
