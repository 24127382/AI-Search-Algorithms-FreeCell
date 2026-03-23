"""Board layout construction mixin for top slots and tableau columns."""

from frontend.board.constants import SLOT_FOUNDATION, SLOT_FREECELL, SLOT_TABLEAU
from frontend.board.slot_widgets import SlotButton, TableauColumnWidget
from frontend.shared.qt import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget, Qt

class BoardUiLayoutMixin:
	"""Build and wire static board layout widgets."""

	def _build_ui(self):
		"""Create top row, tableau section, and base styling."""
		self._apply_board_styles()
		root_layout = QVBoxLayout(self)
		root_layout.setContentsMargins(14, 12, 14, 12)
		root_layout.setSpacing(9)

		root_layout.addWidget(self._create_section_title("FreeCells / Foundations", align_center=False))
		root_layout.addLayout(self._build_top_row())
		root_layout.addWidget(self._create_section_title("Tableau", align_center=True))
		root_layout.addWidget(self._build_tableau_container(), 1)
		root_layout.addLayout(self._build_bottom_info_row())

	def _apply_board_styles(self):
		"""Apply shared stylesheet for board labels and slot buttons."""
		self.setStyleSheet("""
			QLabel {
				color: #f3f8f4;
			}
			QPushButton {
				background-color: rgba(255, 255, 255, 0.07);
				border: 2px solid rgba(255, 255, 255, 0.35);
				border-radius: 8px;
				color: white;
				font-weight: bold;
			}
			QPushButton#SolverReviewControlButton {
				border: 3px solid rgba(255, 255, 255, 0.95);
				border-radius: 8px;
			}
			QPushButton:hover {
				background-color: rgba(255, 255, 255, 0.14);
				border-color: white;
			}
			QPushButton#SolverReviewControlButton:hover {
				border-color: #ffffff;
			}
		""")

	def _create_section_title(self, text: str, align_center: bool) -> QLabel:
		"""Create standardized section header label.

		Args:
			text: Label text.
			align_center: Whether to center-align text.

		Returns:
			QLabel: Configured label widget.
		"""
		label = QLabel(text)
		label.setStyleSheet("font-weight: 700; font-size: 14pt; letter-spacing: 0.5px;")
		if align_center:
			label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
		return label

	def _build_bottom_info_row(self) -> QHBoxLayout:
		"""Build bottom info row with deal number at left corner.

		Returns:
			QHBoxLayout: Bottom info layout.
		"""
		bottom_row = QHBoxLayout()
		bottom_row.setContentsMargins(0, 2, 0, 0)
		bottom_row.setSpacing(8)

		self._deal_number_label = QLabel("Deal #-")
		self._deal_number_label.setObjectName("DealNumberLabel")
		self._deal_number_label.setStyleSheet(
			"font-size: 11pt; font-weight: 700; color: #eef8f1; "
			"background-color: rgba(255, 255, 255, 0.08); "
			"border: 1px solid rgba(255, 255, 255, 0.2); "
			"border-radius: 7px; padding: 4px 8px;"
		)
		self._deal_number_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
		bottom_row.addWidget(self._deal_number_label, alignment=Qt.AlignmentFlag.AlignLeft)
		bottom_row.addStretch(1)

		self._solver_review_controls = QWidget(self)
		review_controls_layout = QHBoxLayout(self._solver_review_controls)
		review_controls_layout.setContentsMargins(0, 0, 0, 0)
		review_controls_layout.setSpacing(8)

		self._list_moves_button = QPushButton("List of move")
		self._list_moves_button.setObjectName("SolverReviewControlButton")
		self._list_moves_button.setFixedWidth(80)
		self._list_moves_button.clicked.connect(self._on_solver_list_moves_clicked)
		review_controls_layout.addWidget(self._list_moves_button)

		self._solver_prev_button = QPushButton("⏮")
		self._solver_prev_button.setObjectName("SolverReviewControlButton")
		self._solver_prev_button.setFixedWidth(30)
		self._solver_prev_button.clicked.connect(self._on_solver_prev_clicked)
		review_controls_layout.addWidget(self._solver_prev_button)

		self._solver_play_pause_button = QPushButton("▶")
		self._solver_play_pause_button.setObjectName("SolverReviewControlButton")
		self._solver_play_pause_button.setFixedWidth(30)
		self._solver_play_pause_button.clicked.connect(self._on_solver_play_pause_clicked)
		review_controls_layout.addWidget(self._solver_play_pause_button)

		self._solver_next_button = QPushButton("⏭")
		self._solver_next_button.setObjectName("SolverReviewControlButton")
		self._solver_next_button.setFixedWidth(30)
		self._solver_next_button.clicked.connect(self._on_solver_next_clicked)
		review_controls_layout.addWidget(self._solver_next_button)

		self._solver_review_controls.setVisible(False)
		bottom_row.addWidget(self._solver_review_controls, alignment=Qt.AlignmentFlag.AlignRight)
		return bottom_row

	def _build_top_row(self) -> QHBoxLayout:
		"""Build row containing freecell and foundation slot buttons.

		Returns:
			QHBoxLayout: Top-row layout.
		"""
		top_row = QHBoxLayout()
		top_row.setSpacing(14)
		top_row.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
		top_row.addStretch()

		for index in range(4):
			button = SlotButton(SLOT_FREECELL, index)
			button.setFixedSize(64, 86)
			button.clicked.connect(lambda _, idx=index: self._on_freecell_clicked(idx))
			button.card_clicked.connect(self._on_slot_source_clicked)
			button.drop_received.connect(self._on_drop_received)
			self._freecell_buttons.append(button)
			top_row.addWidget(button)

		spacer = QLabel(" ")
		spacer.setFixedWidth(24)
		top_row.addWidget(spacer)

		for index in range(4):
			button = SlotButton(SLOT_FOUNDATION, index)
			button.setFixedSize(64, 86)
			button.clicked.connect(lambda _, idx=index: self._on_foundation_clicked(idx))
			button.drop_received.connect(self._on_drop_received)
			self._foundation_buttons.append(button)
			top_row.addWidget(button)

		top_row.addStretch()
		return top_row

	def _build_tableau_container(self):
		"""Build container that hosts all tableau column widgets.

		Returns:
			QWidget: Tableau container widget.
		"""
		tableau_container = QWidget()
		tableau_row = QHBoxLayout(tableau_container)
		tableau_row.setContentsMargins(0, 0, 0, 0)
		tableau_row.setSpacing(14)
		tableau_row.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
		tableau_row.addStretch()

		for col_idx in range(8):
			col_widget = self._create_tableau_column_widget(col_idx)
			tableau_row.addWidget(col_widget)
			if col_idx == 3:
				bottom_spacer = QLabel(" ")
				bottom_spacer.setFixedWidth(24)
				tableau_row.addWidget(bottom_spacer)

		tableau_row.addStretch()
		return tableau_container

	def _create_tableau_column_widget(self, col_idx: int) -> TableauColumnWidget:
		"""Create one tableau column drop area and top target button.

		Args:
			col_idx: Tableau column index.

		Returns:
			TableauColumnWidget: Configured column widget.
		"""
		col_widget = TableauColumnWidget(col_idx)
		col_widget.drop_received.connect(self._on_drop_received)
		col_widget.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
		col_widget.setFixedWidth(64)

		target_button = SlotButton(SLOT_TABLEAU, col_idx)
		target_button.setText("")
		target_button.clicked.connect(lambda _, idx=col_idx: self._on_tableau_target_clicked(idx))
		target_button.card_clicked.connect(self._on_slot_source_clicked)
		target_button.drop_received.connect(self._on_drop_received)
		target_button.setParent(col_widget)
		target_button.move(0, 0)
		target_button.setFixedSize(64, 86)

		self._tableau_buttons.append(target_button)
		self._tableau_layouts.append(col_widget)
		return col_widget

	def _on_card_clicked_dispatcher(self, pos: tuple):
		"""Dispatch card click signals to matching interaction handlers.

		Args:
			pos: Clicked card/slot position tuple.
		"""
		if pos[0] == SLOT_TABLEAU:
			self._on_tableau_card_clicked(pos)
		elif pos[0] == SLOT_FREECELL:
			self._on_freecell_clicked(pos[1])
		elif pos[0] == SLOT_FOUNDATION:
			self._on_foundation_clicked(pos[1])
