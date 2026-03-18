from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QGroupBox, QListWidget, QListWidgetItem, QStyle, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal

class SearchItemWidget(QWidget):
    """Custom widget for history/pinned items with buttons."""
    clicked = pyqtSignal(str)
    pin_requested = pyqtSignal(str)
    remove_requested = pyqtSignal(str, bool) # query, from_pinned

    def __init__(self, text, is_pinned=False):
        super().__init__()
        self.text = text
        self.is_pinned = is_pinned
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        # Main Label
        self.label = QLabel(text)
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.label.setStyleSheet("color: #3791ef; font-size: 14px;")
        # Clickable label logic
        self.label.mousePressEvent = lambda e: self.clicked.emit(self.text)
        layout.addWidget(self.label, 1)

        style = QApplication.instance().style()

        # Pin Button (Star) - Only show in history, not in pinned list itself
        self.btn_pin = QPushButton("★")
        self.btn_pin.setFlat(True)
        self.btn_pin.setFixedSize(20, 20)
        self.btn_pin.setStyleSheet("color: #ffd700; font-size: 14px; border: none;")
        self.btn_pin.setToolTip("Pin to favorites")
        self.btn_pin.clicked.connect(lambda: self.pin_requested.emit(self.text))
        self.btn_pin.setVisible(not is_pinned)
        layout.addWidget(self.btn_pin)

        # Remove Button
        self.btn_remove = QPushButton()
        self.btn_remove.setFlat(True)
        self.btn_remove.setFixedSize(20, 20)
        self.btn_remove.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton))
        self.btn_remove.setToolTip("Remove")
        self.btn_remove.clicked.connect(lambda: self.remove_requested.emit(self.text, self.is_pinned))
        layout.addWidget(self.btn_remove)

class SearchRootView(QWidget):
    def __init__(self, on_search, on_pin=None, on_remove=None, on_clear=None):
        super().__init__()
        self.on_search = on_search
        self.on_pin = on_pin
        self.on_remove = on_remove
        self.on_clear = on_clear

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.layout.setContentsMargins(60, 40, 60, 40)
        self.layout.setSpacing(20)

        # Title
        title = QLabel("Search Library")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #fff;")
        self.layout.addWidget(title)

        # Search Bar
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter search query...")
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 12px;
                font-size: 16px;
                border-radius: 6px;
                border: 1px solid #555;
                background-color: #222;
                color: white;
            }
            QLineEdit:focus {
                border: 1px solid #3791ef;
            }
        """)
        self.search_input.returnPressed.connect(self._do_search)
        
        btn_search = QPushButton("Search")
        btn_search.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_search.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                font-size: 16px;
                background-color: #3791ef;
                color: white;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #4a9ff5;
            }
        """)
        btn_search.clicked.connect(self._do_search)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(btn_search)
        self.layout.addLayout(search_layout)
        
        # Recent / Pinned Sections
        h_layout = QHBoxLayout()
        h_layout.setSpacing(40)
        
        # Style for sections
        group_style = "QGroupBox { font-weight: bold; color: #aaa; font-size: 14px; border: 1px solid #333; border-radius: 8px; margin-top: 10px; padding-top: 10px; }"
        list_style = "QListWidget { border: none; background-color: transparent; outline: none; }"

        # Recent Searches (History)
        recent_group = QGroupBox("🕒 History")
        recent_group.setStyleSheet(group_style)
        recent_vbox = QVBoxLayout(recent_group)
        
        self.recent_list = QListWidget()
        self.recent_list.setStyleSheet(list_style)
        recent_vbox.addWidget(self.recent_list)
        
        self.btn_clear = QPushButton("Clear History")
        self.btn_clear.setFlat(True)
        self.btn_clear.setStyleSheet("color: #888; font-size: 11px; text-align: right;")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(lambda: self.on_clear() if self.on_clear else None)
        recent_vbox.addWidget(self.btn_clear)
        
        # Pinned Searches (Favorites)
        pinned_group = QGroupBox("⭐ Favorites")
        pinned_group.setStyleSheet(group_style)
        pinned_vbox = QVBoxLayout(pinned_group)
        
        self.pinned_list = QListWidget()
        self.pinned_list.setStyleSheet(list_style)
        pinned_vbox.addWidget(self.pinned_list)
        
        h_layout.addWidget(recent_group, 1)
        h_layout.addWidget(pinned_group, 1)
        self.layout.addLayout(h_layout)

    def update_data(self, history, pinned):
        """Re-populate the history and pinned lists."""
        self.recent_list.clear()
        for item_text in history:
            item = QListWidgetItem(self.recent_list)
            widget = SearchItemWidget(item_text, is_pinned=False)
            widget.clicked.connect(self._do_search_query)
            widget.pin_requested.connect(self.on_pin)
            widget.remove_requested.connect(self.on_remove)
            item.setSizeHint(widget.sizeHint())
            self.recent_list.addItem(item)
            self.recent_list.setItemWidget(item, widget)

        self.pinned_list.clear()
        for item_text in pinned:
            item = QListWidgetItem(self.pinned_list)
            widget = SearchItemWidget(item_text, is_pinned=True)
            widget.clicked.connect(self._do_search_query)
            widget.pin_requested.connect(self.on_pin) # Will act as Unpin
            widget.remove_requested.connect(self.on_remove)
            item.setSizeHint(widget.sizeHint())
            self.pinned_list.addItem(item)
            self.pinned_list.setItemWidget(item, widget)
            
        self.btn_clear.setVisible(len(history) > 0)

    def _do_search(self):
        q = self.search_input.text().strip()
        if q:
            self.on_search(q)
            
    def _do_search_query(self, q):
        self.search_input.setText(q)
        self.on_search(q)
