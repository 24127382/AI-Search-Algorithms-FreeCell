"""Mouse interaction handlers for selecting and moving cards on the board."""

from source.domain.model.card import Card
from source.domain.rule.rules import get_movable_sequences
from source.presentation.qt.board.constants import SLOT_FOUNDATION, SLOT_FREECELL, SLOT_TABLEAU
from source.presentation.qt.card.assets import SUIT_SYMBOL


class BoardMoveInteractionMixin:
    """Encapsulates click/double-click interaction rules for board widgets."""

    def _on_slot_source_clicked(self, source: tuple[str, int]):
        """Route slot click by slot type.

        Args:
                source: Clicked source tuple.
        """
        source_type, source_idx = source
        if source_type == SLOT_TABLEAU:
            self._on_tableau_target_clicked(source_idx)
        elif source_type == SLOT_FREECELL:
            self._on_freecell_clicked(source_idx)

    def _on_tableau_card_clicked(self, pos: tuple):
        """Select tableau source or attempt move to clicked column.

        Args:
                pos: Clicked card position tuple.
        """
        if self.is_solver_mode_active():
            self._emit_solver_interaction_locked()
            return
        if self.state is None:
            return

        col_idx = pos[1]
        if not self.state.tableau[col_idx]:
            return

        if self.selected_source is None:
            selection = self._resolve_tableau_selection(col_idx, pos)
            if selection is None:
                return

            source, card_selected = selection
            self._set_source(source)
            self._emit_status(
                f"Selected {card_selected.rank}{SUIT_SYMBOL[card_selected.suit]} in column {col_idx + 1}"
            )
            return

        self._try_move((SLOT_TABLEAU, col_idx))

    def _resolve_tableau_selection(
        self, col_idx: int, pos: tuple
    ) -> tuple[tuple, Card] | None:
        """Resolve tableau selection target.

        Args:
                col_idx: Tableau column index.
                pos: Clicked position tuple.

        Returns:
                tuple[tuple, Card] | None: Selected source and card, or `None`.
        """
        col_cards = self.state.tableau[col_idx]
        top_card = col_cards[-1]
        source = (SLOT_TABLEAU, col_idx)

        if len(pos) != 3:
            return source, top_card

        card_idx = pos[2]
        if col_cards[card_idx] in self._movable_bases(col_cards):
            return pos, col_cards[card_idx]
        if card_idx != len(col_cards) - 1:
            self._emit_status("Cannot move this card.")
            return None
        return source, top_card

    def _movable_bases(self, col_cards: tuple) -> set[Card]:
        """Return set of card bases that can start movable sequences.

        Args:
                col_cards: Tableau column cards.

        Returns:
                set[Card]: Movable sequence base cards.
        """
        return {sequence[0] for sequence in get_movable_sequences(col_cards)}

    def _on_card_double_clicked(self, pos: tuple):
        """Attempt auto-move to foundation, then fallback to freecell.

        Args:
                pos: Double-clicked position tuple.
        """
        if self.is_solver_mode_active():
            self._emit_solver_interaction_locked()
            return
        if self.state is None:
            return

        from_pos_engine = self._resolve_double_click_source(pos)
        if from_pos_engine is None:
            return

        valid_moves = self.game_service.get_valid_moves(self.state, prune_safe=False)

        foundation_move = self._find_first_move(
            valid_moves, from_pos_engine, SLOT_FOUNDATION
        )
        if foundation_move is not None:
            self._apply_automatic_move(
                foundation_move,
                "Automatically moved card to Foundation.",
                check_goal=True,
            )
            return

        freecell_move = self._find_first_move(
            valid_moves, from_pos_engine, SLOT_FREECELL
        )
        if freecell_move is not None:
            self._apply_automatic_move(
                freecell_move, "Automatically moved to FreeCell.", check_goal=False
            )

    def _resolve_double_click_source(self, pos: tuple) -> tuple[str, int] | None:
        """Map clicked tuple into engine-level source position.

        Args:
                pos: Clicked card/slot tuple.

        Returns:
                tuple[str, int] | None: Engine source tuple, or `None`.
        """
        if len(pos) == 3:
            col_idx = pos[1]
            card_idx = pos[2]
            if card_idx == len(self.state.tableau[col_idx]) - 1:
                return (SLOT_TABLEAU, col_idx)
            return None

        if len(pos) == 2:
            return (pos[0], pos[1])

        return None

    def _on_tableau_target_clicked(self, col_idx: int):
        """Select source from tableau or move current selection to this column.

        Args:
                col_idx: Target tableau column index.
        """
        if self.is_solver_mode_active():
            self._emit_solver_interaction_locked()
            return
        if self.selected_source is None:
            card = (
                self.state.tableau[col_idx][-1] if self.state.tableau[col_idx] else None
            )
            if card is None:
                self._emit_status("Column is empty. Select a source card first.")
                return
            self._set_source((SLOT_TABLEAU, col_idx))
            self._emit_status(
                f"Selected {card.rank}{SUIT_SYMBOL[card.suit]} in column {col_idx + 1}"
            )
            return

        self._try_move((SLOT_TABLEAU, col_idx))

    def _on_freecell_clicked(self, cell_idx: int):
        """Select source from freecell or move current selection to freecell.

        Args:
                cell_idx: Freecell index.
        """
        if self.is_solver_mode_active():
            self._emit_solver_interaction_locked()
            return
        if self.selected_source is None:
            card = self.state.freecells[cell_idx]
            if card is None:
                self._emit_status("FreeCell is empty.")
                return
            self._set_source((SLOT_FREECELL, cell_idx))
            self._emit_status(
                f"Selected {card.rank}{SUIT_SYMBOL[card.suit]} in FreeCell {cell_idx + 1}"
            )
            return

        self._try_move((SLOT_FREECELL, cell_idx))

    def _on_foundation_clicked(self, foundation_idx: int):
        """Attempt move from selected source into foundation pile.

        Args:
                foundation_idx: Foundation index.
        """
        if self.is_solver_mode_active():
            self._emit_solver_interaction_locked()
            return
        if self.selected_source is None:
            self._emit_status("Select a source card before moving to Foundation.")
            return
        self._try_move((SLOT_FOUNDATION, foundation_idx))
