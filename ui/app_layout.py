import asyncio
import os
import traceback
import urllib.parse
from pathlib import Path
from urllib.parse import urljoin

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
    QListWidget, QListWidgetItem, QStackedWidget, QLabel, QPushButton, QFrame,
    QDialog, QTextEdit, QMessageBox, QStyle, QApplication, QLineEdit, QScrollArea,
    QLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize, QTimer, QRect, QPoint
from PyQt6.QtGui import QIcon

from config import ConfigManager
from ui.flow_layout import FlowLayout
from ui.views.servers import ServersView
from ui.views.library import LocalLibraryView
from ui.views.library_detail import LocalComicDetailView
from ui.views.local_reader import LocalReaderView
from ui.views.browser import BrowserView
from ui.views.detail import DetailView
from ui.views.reader import ReaderView
from ui.views.settings import SettingsView
from ui.views.downloads import DownloadsView
from ui.views.search_root import SearchRootView
from api.download_manager import DownloadManager
import logger

class MainWindow(QMainWindow):
    def __init__(self, config_manager: ConfigManager):
        super().__init__()
        self.config_manager = config_manager
        self.setWindowTitle("ComicCatcher")
        self.resize(1200, 800)

        self.api_client = None
        self.opds_client = None
        self.image_manager = None
        self.download_manager = None
        
        # Tabbed History State
        self.active_tab = "feed" # "feed" or "search"
        self.feed_history = []
        self.feed_index = -1
        self.search_history = []
        self.search_index = -1

        # Main horizontal layout (Sidebar | Content)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QHBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setFixedWidth(160)
        self.sidebar.setStyleSheet("background-color: #1e1e1e; color: white;")
        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(0, 20, 0, 5)

        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("""
            QListWidget {
                border: none;
                outline: none;
                background-color: transparent;
            }
            QListWidget::item {
                padding: 12px;
                color: #ccc;
                border-left: 3px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #2d2d2d;
                color: white;
                border-left: 3px solid #3791ef;
            }
            QListWidget::item:hover {
                background-color: #252525;
            }
        """)
        self.nav_list.setIconSize(QSize(20, 20))
        
        style = QApplication.instance().style()
        
        def add_nav_item(text, icon_type):
            item = QListWidgetItem(text)
            item.setIcon(style.standardIcon(icon_type))
            self.nav_list.addItem(item)

        add_nav_item("Servers", QStyle.StandardPixmap.SP_ComputerIcon)
        add_nav_item("Settings", QStyle.StandardPixmap.SP_FileDialogDetailedView)
        add_nav_item("Browser", QStyle.StandardPixmap.SP_FileDialogContentsView)
        add_nav_item("Library", QStyle.StandardPixmap.SP_DirHomeIcon)
        add_nav_item("Downloads", QStyle.StandardPixmap.SP_ArrowDown)
        
        self.nav_list.currentRowChanged.connect(self._on_sidebar_changed)
        self.sidebar_layout.addWidget(self.nav_list)
        
        self.layout.addWidget(self.sidebar)

        # Main Vertical Layout (Header | Content)
        self.main_area = QWidget()
        self.main_layout = QVBoxLayout(self.main_area)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.layout.addWidget(self.main_area, 1)

        # Debug Bar (at the very top)
        self.debug_bar = QFrame()
        self.debug_bar.setFixedHeight(25)
        self.debug_bar.setStyleSheet("background-color: #1a1a1a; border-bottom: 1px solid #333;")
        self.debug_layout = QHBoxLayout(self.debug_bar)
        self.debug_layout.setContentsMargins(10, 0, 10, 0)
        self.debug_layout.setSpacing(10)
        
        self.history_counter = QLabel("[0/0]")
        self.history_counter.setStyleSheet("color: #3791ef; font-size: 10px; font-weight: bold;")
        
        self.debug_url_text = QLineEdit("")
        self.debug_url_text.setReadOnly(True)
        self.debug_url_text.setStyleSheet("""
            QLineEdit {
                color: #aaa;
                font-size: 10px;
                background: transparent;
                border: none;
                selection-background-color: #3791ef;
            }
        """)
        
        self.btn_logs = QPushButton("Logs")
        self.btn_logs.setFixedSize(40, 18)
        self.btn_logs.setStyleSheet("font-size: 9px;")
        self.btn_logs.clicked.connect(self._show_logs_dialog)
        
        self.btn_copy = QPushButton("Copy")
        self.btn_copy.setFixedSize(40, 18)
        self.btn_copy.setStyleSheet("font-size: 9px;")
        self.btn_copy.clicked.connect(self._copy_url_to_clipboard)
        
        self.debug_layout.addWidget(self.history_counter)
        self.debug_layout.addWidget(self.debug_url_text, 1)
        self.debug_layout.addWidget(self.btn_copy)
        self.debug_layout.addWidget(self.btn_logs)
        
        self.main_layout.addWidget(self.debug_bar)
        self.debug_bar.setVisible(os.getenv("DEBUG") == "1")

        # Top Header (Server Info + Tabs + Breadcrumbs)
        self.top_header = QFrame()
        self.top_header.setStyleSheet("background-color: #252526; border-bottom: 1px solid #333;")
        self.header_layout = QVBoxLayout(self.top_header)
        self.header_layout.setContentsMargins(10, 5, 10, 5)
        self.header_layout.setSpacing(5)

        # Row 1: Server Info & Tabs
        self.server_row = QHBoxLayout()
        self.server_icon_label = QLabel()
        self.server_name_label = QLabel("No Server Selected")
        self.server_name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: white;")
        
        self.btn_tab_feed = QPushButton("Feed")
        self.btn_tab_feed.setCheckable(True)
        self.btn_tab_feed.setChecked(True)
        self.btn_tab_feed.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_feed.clicked.connect(lambda: self._on_tab_clicked("feed"))
        
        self.btn_tab_search = QPushButton("Search")
        self.btn_tab_search.setCheckable(True)
        self.btn_tab_search.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tab_search.clicked.connect(lambda: self._on_tab_clicked("search"))
        
        tab_style = """
            QPushButton { padding: 6px 15px; border: none; font-size: 14px; font-weight: bold; color: #888; background: transparent; }
            QPushButton:checked { color: white; border-bottom: 2px solid #3791ef; }
            QPushButton:hover:!checked { color: #ccc; }
        """
        self.btn_tab_feed.setStyleSheet(tab_style)
        self.btn_tab_search.setStyleSheet(tab_style)
        
        self.server_row.addWidget(self.server_icon_label)
        self.server_row.addWidget(self.server_name_label)
        self.server_row.addSpacing(20)
        self.server_row.addWidget(self.btn_tab_feed)
        self.server_row.addWidget(self.btn_tab_search)
        self.server_row.addStretch()
        self.header_layout.addLayout(self.server_row)

        # Row 2: Breadcrumb Row
        self.breadcrumb_container = QFrame()
        self.breadcrumb_row = QHBoxLayout(self.breadcrumb_container)
        self.breadcrumb_row.setContentsMargins(0, 0, 0, 0)
        self.breadcrumb_row.setSpacing(10)
        
        self.breadcrumb_inner = QWidget()
        self.breadcrumb_items_layout = FlowLayout(self.breadcrumb_inner, spacing=5)
        
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setFixedSize(60, 25)
        self.btn_refresh.clicked.connect(self.on_manual_refresh)
        
        self.breadcrumb_row.addWidget(self.breadcrumb_inner, 1)
        self.breadcrumb_row.addWidget(self.btn_refresh, 0, Qt.AlignmentFlag.AlignTop)
        
        self.header_layout.addWidget(self.breadcrumb_container)
        
        self.main_layout.addWidget(self.top_header)

        # Content Area
        self.content_stack = QStackedWidget()
        self.main_layout.addWidget(self.content_stack)

        # Initialize Views
        self.servers_view = ServersView(self.config_manager, self.on_profile_selected)
        self.servers_view.icon_loaded.connect(self._on_server_icon_loaded)
        self.settings_view = SettingsView(self.config_manager)
        
        # Dual Browser Views
        self.feed_browser_view = BrowserView(self.config_manager, self.on_open_detail, self.on_navigate_to_url, on_offset_change=self._on_browser_offset_changed)
        self.search_browser_view = BrowserView(self.config_manager, self.on_open_detail, self.on_navigate_to_url, on_offset_change=self._on_browser_offset_changed)
        self.search_root_view = SearchRootView(
            on_search=lambda q: asyncio.create_task(self._execute_search(q)),
            on_pin=self._on_pin_search,
            on_remove=self._on_remove_search,
            on_clear=self._on_clear_search
        )
        
        self.local_library_view = LocalLibraryView(self.config_manager, self.on_open_local_comic)
        self.local_detail_view = LocalComicDetailView(self.on_back_to_local_library, self.on_read_local_comic)
        self.local_reader_view = LocalReaderView(self.on_exit_reader)
        
        self.detail_view = DetailView(self.config_manager, self.on_back_to_browser, self.on_read_book, self.on_navigate_to_url, self.on_start_download, self.on_open_detail)
        self.reader_view = ReaderView(self.config_manager, self.on_exit_reader)
        self.downloads_view = DownloadsView(None)

        self.content_stack.addWidget(self.servers_view)        # 0
        self.content_stack.addWidget(self.settings_view)       # 1
        self.content_stack.addWidget(self.feed_browser_view)   # 2
        self.content_stack.addWidget(self.local_library_view)  # 3
        self.content_stack.addWidget(self.downloads_view)      # 4
        self.content_stack.addWidget(self.local_detail_view)   # 5
        self.content_stack.addWidget(self.local_reader_view)   # 6
        self.content_stack.addWidget(self.detail_view)         # 7
        self.content_stack.addWidget(self.reader_view)         # 8
        self.content_stack.addWidget(self.search_root_view)    # 9
        self.content_stack.addWidget(self.search_browser_view) # 10

        self.nav_list.setCurrentRow(0)
        self.update_header()

    def get_current_history(self):
        if self.active_tab == "search":
            return self.search_history, self.search_index
        return self.feed_history, self.feed_index

    def set_current_history(self, history, index):
        if self.active_tab == "search":
            self.search_history = history
            self.search_index = index
        else:
            self.feed_history = history
            self.feed_index = index

    def _on_sidebar_changed(self, index):
        if index == 2:
            # We clicked "Browser" in the sidebar
            self._on_tab_clicked(self.active_tab)
            return
            
        self.content_stack.setCurrentIndex(index)
        self.top_header.setVisible(index not in (6, 8))

    def _on_tab_clicked(self, tab_name):
        self.active_tab = tab_name
        self.btn_tab_feed.setChecked(tab_name == "feed")
        self.btn_tab_search.setChecked(tab_name == "search")
        
        hist, idx = self.get_current_history()
        
        if tab_name == "search" and (not hist or hist[idx]["type"] == "search_root"):
            self.content_stack.setCurrentIndex(9) # Search Root
            if self.api_client:
                p = self.api_client.profile
                self.search_root_view.update_data(p.search_history, p.pinned_searches)
            self.search_root_view.search_input.setFocus()
        elif idx >= 0:
            entry = hist[idx]
            if entry["type"] == "browser":
                if tab_name == "feed":
                    self.content_stack.setCurrentIndex(2)
                    self.feed_browser_view.setFocus()
                else:
                    self.content_stack.setCurrentIndex(10)
                    self.search_browser_view.setFocus()
            elif entry["type"] == "detail":
                # Detail view is shared, re-render it
                self.detail_view.load_publication(entry["pub"], entry["url"], self.api_client, self.opds_client, self.image_manager)
                self.content_stack.setCurrentIndex(7)
                
        self.update_header()

    def _on_browser_offset_changed(self, offset):
        hist, idx = self.get_current_history()
        if idx >= 0 and hist[idx]["type"] == "browser":
            hist[idx]["offset"] = offset

    def _on_server_icon_loaded(self, profile_id, pixmap):
        # Update server icon in header if active
        if self.api_client and self.api_client.profile.id == profile_id:
            self.server_icon_label.setPixmap(pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def update_header(self):
        # 1. Update Debug Bar (independent of header visibility)
        is_debug_on = os.getenv("DEBUG") == "1"
        current_view_idx = self.content_stack.currentIndex()
        is_reader = current_view_idx in (6, 8)
        
        self.debug_bar.setVisible(is_debug_on and not is_reader)
        
        hist, idx = self.get_current_history()
        if is_debug_on:
            self.history_counter.setText(f"[{idx + 1}/{len(hist)}]")
            if idx >= 0:
                active_entry = hist[idx]
                url_val = active_entry.get("url", "")
                self.debug_url_text.setText(url_val)
                self.debug_url_text.setCursorPosition(0) # Keep start visible
                self.debug_url_text.setToolTip(url_val)
            else:
                self.debug_url_text.setText("")

        # 2. Clear existing breadcrumbs
        while self.breadcrumb_items_layout.count():
            layout_item = self.breadcrumb_items_layout.takeAt(0)
            if layout_item.widget():
                layout_item.widget().deleteLater()
        
        # 3. Determine if Main Header (Tabs/Breadcrumbs) should be visible
        # Only visible in Browser, Detail, or Search views
        show_main_header = not is_reader and current_view_idx in (2, 7, 9, 10)
        self.top_header.setVisible(show_main_header)
        
        if not show_main_header:
            return
        
        style = QApplication.instance().style()

        # 4. Build breadcrumbs
        for i, entry in enumerate(hist):
            title = entry.get("title", "...")
            
            item_widget = QWidget()
            item_layout = QHBoxLayout(item_widget)
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(5)
            
            if i == 0:
                # First breadcrumb gets a tab-specific icon
                if self.active_tab == "feed":
                    icon = style.standardIcon(QStyle.StandardPixmap.SP_DirHomeIcon)
                else:
                    icon = style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView)
                
                if i == idx:
                    icon_label = QLabel()
                    icon_label.setPixmap(icon.pixmap(16, 16))
                    item_layout.addWidget(icon_label)
                else:
                    btn = QPushButton()
                    btn.setIcon(icon)
                    btn.setFlat(True)
                    btn.setFixedSize(20, 20)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.clicked.connect(lambda _, x=i: self.on_jump_to_history(x))
                    item_layout.addWidget(btn)
            else:
                if i == idx:
                    label = QLabel(title)
                    label.setStyleSheet("font-weight: bold; color: #3791ef; font-size: 14px;")
                    item_layout.addWidget(label)
                else:
                    btn = QPushButton(title)
                    btn.setFlat(True)
                    btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    btn.setStyleSheet("text-align: left; padding: 2px; color: #ccc; font-size: 14px;")
                    btn.clicked.connect(lambda _, x=i: self.on_jump_to_history(x))
                    item_layout.addWidget(btn)
            
            self.breadcrumb_items_layout.addWidget(item_widget)
                
            if i < len(hist) - 1:
                sep = QLabel(">")
                sep.setStyleSheet("color: #666;")
                self.breadcrumb_items_layout.addWidget(sep)

        # 5. Force layout refresh
        self.breadcrumb_inner.updateGeometry()
        self.top_header.updateGeometry()

    def on_profile_selected(self, profile):
        from api.client import APIClient
        from api.opds_v2 import OPDS2Client
        from api.image_manager import ImageManager
        
        self.api_client = APIClient(profile)
        self.opds_client = OPDS2Client(self.api_client)
        self.image_manager = ImageManager(self.api_client)
        self.download_manager = DownloadManager(self.api_client, self.config_manager.get_library_dir())
        
        self.feed_browser_view.load_profile(profile)
        self.search_browser_view.load_profile(profile)
        self.reader_view.api_client = self.api_client
        self.downloads_view.dm = self.download_manager
        self.download_manager.set_callback(self.downloads_view.refresh_tasks)
        
        # Initialize isolated histories
        base_url = profile.url
        start_url = base_url if "opds" in base_url.lower() else urljoin(base_url, "/codex/opds/v2.0/")
        
        self.feed_history = [{"type": "browser", "title": "Home", "url": start_url, "offset": 0, "profile_id": profile.id}]
        self.feed_index = 0
        self.search_history = [{"type": "search_root", "title": "Search", "profile_id": profile.id}]
        self.search_index = 0
        self.active_tab = "feed"
        
        # Populate Search Dash
        self.search_root_view.update_data(profile.search_history, profile.pinned_searches)
        
        # Set Header Identity
        self.server_name_label.setText(profile.name)
        icon = getattr(profile, "_cached_icon", None)
        if icon:
            self.server_icon_label.setPixmap(icon.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            style = QApplication.instance().style()
            self.server_icon_label.setPixmap(style.standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon).pixmap(24, 24))
            if not profile.icon_url:
                asyncio.create_task(self.servers_view.discover_and_save_icon(profile))
        
        self.nav_list.setCurrentRow(2) # Switches to Browser view routing
        # Manually trigger load for the root
        asyncio.create_task(self.feed_browser_view.load_feed(start_url, "Home"))
        self.content_stack.setCurrentIndex(2)
        self.update_header()

    async def _execute_search(self, query: str):
        if not self.api_client: return
        p = self.api_client.profile
        
        # 1. Update Search History (Move to front if dupe)
        if query in p.search_history:
            p.search_history.remove(query)
        p.search_history.insert(0, query)
        p.search_history = p.search_history[:50] # Cap at 50
        self.config_manager.update_profile(p)

        # We need to find the search template URL. Load root feed via feed tab's start url (first entry)
        if not self.feed_history: return
        start_url = self.feed_history[0]["url"]
        
        try:
            feed = await self.opds_client.get_feed(start_url)
            search_link = None
            for link in (feed.links or []):
                rel = link.rel
                rels = [rel] if isinstance(rel, str) else (rel or [])
                if "search" in rels:
                    search_link = link.href
                    break
            
            if not search_link:
                QMessageBox.warning(self, "Search", "Search is not supported by this server.")
                return
                
            safe_query = urllib.parse.quote(query)
            if "{?query}" in search_link:
                search_url = search_link.replace("{?query}", f"?query={safe_query}")
            elif "{searchTerms}" in search_link:
                search_url = search_link.replace("{searchTerms}", safe_query)
            else:
                search_url = f"{search_link}?query={safe_query}"
                
            full_search_url = urljoin(start_url, search_url)
            
            ic = self.feed_history[0].get("icon") if self.feed_history else None
            pid = self.feed_history[0].get("profile_id") if self.feed_history else None
            
            self.on_navigate_to_url(full_search_url, title=f"Search: '{query}'", icon=ic, profile_id=pid)
            
        except Exception as e:
            QMessageBox.warning(self, "Search Error", f"Could not perform search: {e}")

    def _on_pin_search(self, query):
        if not self.api_client: return
        p = self.api_client.profile
        if query in p.pinned_searches:
            p.pinned_searches.remove(query)
        else:
            p.pinned_searches.append(query)
        self.config_manager.update_profile(p)
        self.search_root_view.update_data(p.search_history, p.pinned_searches)

    def _on_remove_search(self, query, from_pinned):
        if not self.api_client: return
        p = self.api_client.profile
        if from_pinned:
            if query in p.pinned_searches:
                p.pinned_searches.remove(query)
        else:
            if query in p.search_history:
                p.search_history.remove(query)
        self.config_manager.update_profile(p)
        self.search_root_view.update_data(p.search_history, p.pinned_searches)

    def _on_clear_search(self):
        if not self.api_client: return
        p = self.api_client.profile
        p.search_history.clear()
        self.config_manager.update_profile(p)
        self.search_root_view.update_data(p.search_history, p.pinned_searches)

    def on_navigate_to_url(self, url, title="Loading...", replace=False, keep_title=False, icon=None, profile_id=None):
        hist, idx = self.get_current_history()
        
        if replace and idx >= 0:
            hist[idx]["url"] = url
            if not keep_title:
                hist[idx]["title"] = title
            if icon:
                hist[idx]["icon"] = icon
        else:
            if idx < len(hist) - 1:
                hist = hist[:idx + 1]

            pid = profile_id
            if not pid and idx >= 0:
                pid = hist[idx].get("profile_id")
                
            ic = icon if len(hist) == 0 else None

            hist.append({
                "type": "browser", 
                "title": title, 
                "url": url, 
                "pub": None, 
                "icon": ic,
                "profile_id": pid,
                "offset": 0
            })
            idx = len(hist) - 1
            
        self.set_current_history(hist, idx)
        self.content_stack.setCurrentIndex(10 if self.active_tab == "search" else 2)
        self.update_header()
        
        browser = self.search_browser_view if self.active_tab == "search" else self.feed_browser_view
        asyncio.create_task(browser.load_feed(url, title))
        browser.setFocus()

    def on_open_detail(self, pub, self_url):
        hist, idx = self.get_current_history()
        if idx < len(hist) - 1:
            hist = hist[:idx + 1]

        pid = hist[idx].get("profile_id") if idx >= 0 else None

        hist.append({
            "type": "detail", 
            "title": pub.metadata.title, 
            "url": self_url, 
            "pub": pub,
            "profile_id": pid
        })
        idx = len(hist) - 1
        self.set_current_history(hist, idx)
        
        self.content_stack.setCurrentIndex(7)
        self.update_header()
        self.detail_view.load_publication(pub, self_url, self.api_client, self.opds_client, self.image_manager)

    def on_jump_to_history(self, index):
        hist, _ = self.get_current_history()
        hist = hist[:index + 1]
        self.set_current_history(hist, index)
        
        entry = hist[index]
        if entry["type"] == "browser":
            self.content_stack.setCurrentIndex(10 if self.active_tab == "search" else 2)
        elif entry["type"] == "search_root":
            self.content_stack.setCurrentIndex(9)
        else:
            self.content_stack.setCurrentIndex(7)
            
        self.update_header()
        
        if entry["type"] == "browser":
            browser = self.search_browser_view if self.active_tab == "search" else self.feed_browser_view
            asyncio.create_task(browser.load_feed(entry["url"], entry["title"], initial_offset=entry.get("offset", 0)))
            browser.setFocus()
        elif entry["type"] == "search_root":
            if self.api_client:
                p = self.api_client.profile
                self.search_root_view.update_data(p.search_history, p.pinned_searches)
            self.search_root_view.search_input.setFocus()
        else:
            self.detail_view.load_publication(entry["pub"], entry["url"], self.api_client, self.opds_client, self.image_manager)

    def on_manual_refresh(self):
        hist, idx = self.get_current_history()
        if idx < 0: return
        entry = hist[idx]
        if entry["type"] == "browser":
            browser = self.search_browser_view if self.active_tab == "search" else self.feed_browser_view
            asyncio.create_task(browser.load_feed(entry["url"], entry["title"], force_refresh=True, initial_offset=entry.get("offset", 0)))
        elif entry["type"] == "search_root":
            if self.api_client:
                p = self.api_client.profile
                self.search_root_view.update_data(p.search_history, p.pinned_searches)
        else:
            # Detail View
            self.detail_view.load_publication(entry["pub"], entry["url"], self.api_client, self.opds_client, self.image_manager, force_refresh=True)

    def _copy_url_to_clipboard(self):
        url = self.debug_url_text.text()
        if url:
            QApplication.clipboard().setText(url)

    def _show_logs_dialog(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("System Logs")
        dialog.resize(800, 600)
        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setStyleSheet("font-family: monospace; font-size: 10px; background-color: #1e1e1e; color: #ddd;")
        try:
            if os.path.exists("comiccatcher.log"):
                with open("comiccatcher.log", "r") as f:
                    text_edit.setPlainText("".join(f.readlines()[-200:]))
            else:
                text_edit.setPlainText("Log file not found.")
        except Exception as e:
            text_edit.setPlainText(f"Error reading logs: {e}")
        layout.addWidget(text_edit)
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(dialog.accept)
        layout.addWidget(btn_close)
        dialog.exec()

    def on_read_book(self, pub, manifest_url):
        self.reader_view.load_manifest(pub, manifest_url)
        self.content_stack.setCurrentIndex(8)
        self.sidebar.hide()
        self.top_header.hide()

    def on_start_download(self, pub, url):
        if self.download_manager:
            asyncio.create_task(self.download_manager.start_download(pub.id, pub.metadata.title, url))
            self.nav_list.setCurrentRow(4)

    def on_open_local_comic(self, path):
        self.local_detail_view.load_path(path)
        self.content_stack.setCurrentIndex(5)

    def on_back_to_local_library(self):
        self.content_stack.setCurrentIndex(3)

    def on_back_to_browser(self):
        hist, idx = self.get_current_history()
        for i in range(idx - 1, -1, -1):
            if hist[i]["type"] == "browser" or hist[i]["type"] == "search_root":
                self.on_jump_to_history(i)
                return
        self.nav_list.setCurrentRow(0)

    def on_read_local_comic(self, path):
        self.local_reader_view.load_cbz(path)
        self.content_stack.setCurrentIndex(6)
        self.sidebar.hide()
        self.top_header.hide()

    def on_exit_reader(self):
        self.sidebar.show()
        self.top_header.show()
        if self.content_stack.currentIndex() == 6:
            self.content_stack.setCurrentIndex(5)
        else:
            self.content_stack.setCurrentIndex(7)
            # Refresh to show new progress
            self.on_manual_refresh()
