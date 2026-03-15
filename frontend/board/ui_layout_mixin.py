from frontend.board.constants import SLOT_FOUNDATION, SLOT_FREECELL, SLOT_TABLEAU
from frontend.board.slot_widgets import SlotButton, TableauColumnWidget
from frontend.shared.qt import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget, Qt

class BoardUiLayoutMixin:
	def _build_ui(self):
		self._apply_board_styles()
		root_layout = QVBoxLayout(self)
		root_layout.setContentsMargins(14, 12, 14, 12)
		root_layout.setSpacing(9)

		root_layout.addWidget(self._create_section_title("FreeCells / Foundations", align_center=False))
		root_layout.addLayout(self._build_top_row())
		root_layout.addWidget(self._create_section_title("Tableau", align_center=True))
		root_layout.addWidget(self._build_tableau_container(), 1)

	def _apply_board_styles(self):
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
			QPushButton:hover {
				background-color: rgba(255, 255, 255, 0.14);
				border-color: white;
			}
		""")

	def _create_section_title(self, text: str, align_center: bool) -> QLabel:
		label = QLabel(text)
		label.setStyleSheet("font-weight: 700; font-size: 14pt; letter-spacing: 0.5px;")
		if align_center:
			label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
		return label

	def _build_top_row(self) -> QHBoxLayout:
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
		if pos[0] == SLOT_TABLEAU:
			self._on_tableau_card_clicked(pos)
		elif pos[0] == SLOT_FREECELL:
			self._on_freecell_clicked(pos[1])
		elif pos[0] == SLOT_FOUNDATION:
			self._on_foundation_clicked(pos[1])
