"""Board rendering mixin that maps state objects to Qt widgets."""

from source.domain.model.card import VALID_SUITS
from source.domain.rule.rules import get_movable_sequences
from source.presentation.qt.board.constants import SLOT_FOUNDATION, SLOT_FREECELL, SLOT_TABLEAU
from source.presentation.qt.card.assets import SUIT_SYMBOL
from source.presentation.qt.card.widget import CardWidget
from source.presentation.qt.shared.animation import animate_move, fade_in
from source.presentation.qt.shared.qt import QPoint
from source.presentation.qt.shared.sound import play_card_drop_sound

_DEAL_ANIMATION_DURATION_MS = 120


class BoardUiRenderMixin:
    """Render freecells, foundations, tableau, and card widget transitions."""

    def _cancel_deal_shuffle_animation(self):
        """Stop pending deal-shuffle timers to avoid stale animations."""
        self._deal_shuffle_active = False

    def _update_card_widget(
        self,
        card,
        new_parent,
        new_pos,
        pos_tuple,
        payload_str,
        is_draggable,
        drag_sequence,
        is_selected,
    ):
        """Create/reparent/move one `CardWidget` and update interaction state.

        Args:
                card: Card model instance.
                new_parent: Target parent widget.
                new_pos: Target widget position.
                pos_tuple: Logical card position tuple.
                payload_str: Drag payload string.
                is_draggable: Whether card should be draggable.
                drag_sequence: Sequence used for stacked drag preview.
                is_selected: Whether card should render selected highlight.
        """
        card_widget = self._card_registry.get(card)
        if isinstance(new_pos, tuple):
            new_pos = QPoint(int(new_pos[0]), int(new_pos[1]))
        if card_widget is None:
            card_widget = CardWidget(card, pos_tuple, new_parent)
            card_widget.clicked.connect(self._on_card_clicked_dispatcher)
            card_widget.double_clicked.connect(self._on_card_double_clicked)
            card_widget.drop_received.connect(self._on_drop_received)
            self._card_registry[card] = card_widget
            card_widget.move(new_pos)
            card_widget.show()
            fade_in(card_widget, duration=150)
        else:
            card_widget.position = pos_tuple
            old_parent = card_widget.parent()
            if old_parent != new_parent and old_parent is not None:
                old_global = old_parent.mapToGlobal(card_widget.pos())
                card_widget.setParent(new_parent)
                start_pos = new_parent.mapFromGlobal(old_global)
                card_widget.move(start_pos)
                card_widget.show()
            elif old_parent is None:
                card_widget.setParent(new_parent)
                card_widget.move(new_pos)
                card_widget.show()

            if card_widget.pos() != new_pos:
                if getattr(self, "_is_deal_shuffle_setup", False):
                    card_widget.move(new_pos)
                else:
                    animate_move(card_widget, card_widget.pos(), new_pos, duration=220)
            else:
                card_widget.move(new_pos)

        card_widget.set_drag_payload(payload_str, is_draggable, drag_sequence)
        card_widget.set_selected(is_selected)
        if not (
            getattr(self, "_deal_shuffle_active", False)
            and getattr(card_widget, "_deal_hidden", False)
        ):
            card_widget.show()
        card_widget.raise_()

    def _render(self):
        """Render full board from current state and emit updated move count."""
        if self.state is None:
            return

        is_shuffle_setup = bool(
            getattr(self, "_play_deal_shuffle_on_next_render", False)
        )
        self._is_deal_shuffle_setup = is_shuffle_setup

        self.setUpdatesEnabled(False)
        try:
            self._render_freecells()
            self._render_foundations()
            self._render_tableau()
            if is_shuffle_setup:
                self._play_deal_shuffle_animation_if_needed()
        finally:
            self._is_deal_shuffle_setup = False
            self.setUpdatesEnabled(True)
            self.update()

        self.move_count_changed.emit(self.move_count)

    def _play_deal_shuffle_animation_if_needed(self):
        """Run one-shot deal animation when a new table is initialized."""
        if not getattr(self, "_play_deal_shuffle_on_next_render", False):
            return
        self._cancel_deal_shuffle_animation()
        self._play_deal_shuffle_on_next_render = False

        if self.state is None or not self._card_registry:
            return

        all_widgets = [
            widget
            for widget in self._card_registry.values()
            if widget.parentWidget() is not None
        ]
        if not all_widgets:
            self._deal_shuffle_active = False
            return

        random_tableau = self.game_service.deal_by_game_number(
            self.game_service.random_deal_number()
        )
        random_start_positions = self._build_random_deal_positions(random_tableau)

        self._deal_shuffle_active = True
        play_card_drop_sound()

        for widget in all_widgets:
            parent_widget = widget.parentWidget()
            target_pos = QPoint(widget.pos())
            start_global = random_start_positions.get(widget.card)
            if start_global is None:
                continue
            start_pos = parent_widget.mapFromGlobal(start_global)
            widget.move(start_pos)
            widget.show()
            widget.raise_()
            animate_move(
                widget,
                start_pos,
                target_pos,
                duration=_DEAL_ANIMATION_DURATION_MS,
                play_sound=False,
            )

        self._enforce_card_layering()

        self._deal_shuffle_active = False

    def _enforce_card_layering(self):
        """Restore deterministic z-order so card stacks render in correct layers."""
        if self.state is None:
            return

        for card in self.state.freecells:
            if card is None:
                continue
            widget = self._card_registry.get(card)
            if widget is not None:
                widget.raise_()

        for foundation_cards in self.state.foundations:
            for card in foundation_cards:
                widget = self._card_registry.get(card)
                if widget is not None:
                    widget.raise_()

        for col_cards in self.state.tableau:
            for card in col_cards:
                widget = self._card_registry.get(card)
                if widget is not None:
                    widget.raise_()

    def _build_random_deal_positions(self, random_tableau) -> dict:
        """Build global card positions from a random deal layout."""
        positions = {}
        for col_idx, col_cards in enumerate(random_tableau):
            column_widget = self._tableau_layouts[col_idx]
            for row_idx, card in enumerate(col_cards):
                local_pos = QPoint(0, row_idx * 30)
                positions[card] = column_widget.mapToGlobal(local_pos)
        return positions

    def _emit_status(self, message: str):
        """Forward status text through widget-level status signal.

        Args:
                message: Status text to emit.
        """
        self.status_changed.emit(message)

    def _render_freecells(self):
        """Render freecell slots and corresponding card widgets."""
        for idx, button in enumerate(self._freecell_buttons):
            card = self.state.freecells[idx]
            selected = self.selected_source == (SLOT_FREECELL, idx)

            if card:
                bg = "#f8f9fa"
                color = "#c0392b" if card.suit in ("hearts", "diamonds") else "#1f2d3d"
                border = "4px solid #ffeb3b" if selected else "1px solid #2c3e50"
                self._update_card_widget(
                    card,
                    button,
                    (0, 0),
                    (SLOT_FREECELL, idx),
                    f"freecell:{idx}",
                    True,
                    [],
                    selected,
                )
            else:
                bg = "rgba(255,255,255,0)"
                color = "white"
                border = "4px solid #ffffff"

            button.set_drag_payload(f"freecell:{idx}", card is not None)
            button.setStyleSheet(
                f"text-align: center; margin: 0px 7px; border: {border}; background-color: {bg}; color: {color}; font-size: 14pt; border-radius: 8px;"
            )

    def _render_foundations(self):
        """Render foundation slots, suit targets, and stacked cards."""
        for idx, button in enumerate(self._foundation_buttons):
            foundation_cards = self.state.foundations[idx]
            top_card = foundation_cards[-1] if foundation_cards else None
            required_suit = VALID_SUITS[idx]
            target_symbol = SUIT_SYMBOL[required_suit]
            button.set_drag_payload("", False)

            if top_card:
                button.setText("")
                bg = "#f8f9fa"
                color = (
                    "#c0392b" if top_card.suit in ("hearts", "diamonds") else "#1f2d3d"
                )
                border = "1px solid #2c3e50"
                font_size = "14px"
                for card in foundation_cards:
                    self._update_card_widget(
                        card,
                        button,
                        (0, 0),
                        (SLOT_FOUNDATION, idx),
                        "",
                        False,
                        [],
                        False,
                    )
            else:
                button.setText(target_symbol)
                bg = "rgba(255,255,255,0)"
                color = (
                    "#c0392b" if required_suit in ("hearts", "diamonds") else "black"
                )
                border = "4px solid #ffffff"
                font_size = "32px"

            button.setStyleSheet(
                f"text-align: center; margin: 0px 7px; border: {border}; background-color: {bg}; color: {color}; font-size: {font_size}; border-radius: 8px;"
            )

    def _render_tableau(self):
        """Render tableau columns, movable cards, and column selection indicators."""
        for col_idx, col_cards in enumerate(self.state.tableau):
            movable_bases = {
                sequence[0] for sequence in get_movable_sequences(col_cards)
            }

            for card_idx, card in enumerate(col_cards):
                is_top = card_idx == len(col_cards) - 1
                is_draggable = card in movable_bases
                drag_sequence = col_cards[card_idx:] if is_draggable else []
                is_selected = self._is_selected_tableau_card(
                    col_idx, card_idx, is_draggable, is_top
                )

                self._update_card_widget(
                    card,
                    self._tableau_layouts[col_idx],
                    (0, card_idx * 30),
                    (SLOT_TABLEAU, col_idx, card_idx),
                    f"tableau:{col_idx}:{card_idx}",
                    is_draggable,
                    drag_sequence,
                    is_selected,
                )

            col_selected = self.selected_source == (SLOT_TABLEAU, col_idx)
            border = "3px solid #ffeb3b" if col_selected else "4px solid #ffffff"
            self._tableau_buttons[col_idx].set_drag_payload(
                f"tableau:{col_idx}", bool(col_cards)
            )
            self._tableau_buttons[col_idx].setStyleSheet(
                f"margin: 0px 7px; border: {border};"
            )

    def _is_selected_tableau_card(
        self, col_idx: int, card_idx: int, is_draggable: bool, is_top: bool
    ) -> bool:
        """Check whether tableau card should show selected highlight.

        Args:
                col_idx: Tableau column index.
                card_idx: Card index in tableau column.
                is_draggable: Whether card is currently draggable.
                is_top: Whether card is top card in column.

        Returns:
                bool: `True` when selected highlight should be shown.
        """
        if not is_draggable or not self.selected_source:
            return False
        if self.selected_source[:2] != (SLOT_TABLEAU, col_idx):
            return False
        if len(self.selected_source) == 3:
            return self.selected_source[2] == card_idx
        return len(self.selected_source) == 2 and is_top
