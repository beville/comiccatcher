import sys
import asyncio
import math
import os
from unittest.mock import MagicMock, AsyncMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QSize
from qasync import QEventLoop

# Import the actual code
from ui.views.browser import BrowserView
from config import ConfigManager
from models.opds import OPDSFeed, Metadata, Publication, Link

async def test_viewport_sequence():
    app = QApplication.instance() or QApplication(sys.argv)
    
    # 1. Setup mocks
    config = MagicMock(spec=ConfigManager)
    config.get_scroll_method.return_value = "viewport"
    
    # Fake callbacks
    def on_detail(p, u): pass
    def on_nav(u, t, **kwargs): pass
    
    view = BrowserView(config, on_detail, on_nav)
    
    # Setup API client mock
    api_client = MagicMock()
    api_client.profile.get_base_url.return_value = "http://fake"
    view.api_client = api_client
    view.opds_client = MagicMock()
    
    # Force viewport dimensions: 
    # To get exactly 15 items per screen in PUB mode (275 per row, 175 per col)
    # We need 3 rows (3*275 + 20 margin = 845) and 5 cols (5*175 + 20 margin = 895)
    # Wait, user's log was 15x1. That's NAV mode.
    # NAV mode: available_h // 45. 15 * 45 + 20 = 695.
    
    view.scroll.viewport().height = MagicMock(return_value=695)
    view.scroll.viewport().width = MagicMock(return_value=1040)
    
    total_items = 3188
    # No publications -> NAV mode
    fake_nav = [Link(title=f"Nav {i}", href=f"href{i}") for i in range(100)]
    
    feed = OPDSFeed(
        metadata=Metadata(title="Test Feed", numberOfItems=total_items, itemsPerPage=100, currentPage=1),
        links=[],
        navigation=fake_nav
    )
    
    # Use AsyncMock for get_feed
    view.opds_client.get_feed = AsyncMock(return_value=feed)
    
    print(f"--- Initializing Feed with {total_items} items ---")
    await view.load_feed("http://fake", "Test")
    
    # Wait for logic to process
    await asyncio.sleep(0.1)
    
    print(f"Initial Mode: {'PUB' if view.is_pub_mode else 'NAV'}")
    print(f"Items/Screen: {view.items_per_screen}")
    print(f"Initial State: {view.viewport_paging_bar.label_status.text()}")
    
    # 2. Simulate Jump to Last
    print("\n--- Simulating Jump to Last ---")
    view.last_url = "http://fake/last"
    
    # Page 32 starts at 3100.
    last_nav = [Link(title=f"Nav {i}", href=f"href{i}") for i in range(3100, 3188)]
    last_feed = OPDSFeed(
        metadata=Metadata(title="Test Feed", numberOfItems=total_items, itemsPerPage=100, currentPage=32),
        links=[],
        navigation=last_nav
    )
    view.opds_client.get_feed = AsyncMock(return_value=last_feed)
    
    # Trigger the jump
    await view._fetch_absolute_last()
    
    # Wait for UI settle logic
    await asyncio.sleep(0.1)
    
    status = view.viewport_paging_bar.label_status.text()
    actual_start = view.buffer_absolute_offset + view.viewport_offset
    expected_scr = math.ceil(total_items / view.items_per_screen)
    expected_start = ((total_items - 1) // view.items_per_screen) * view.items_per_screen
    
    print(f"Final State: {status}")
    print(f"Effective Global Start: {actual_start}")
    print(f"Expected Global Start: {expected_start}")
    print(f"Expected Screen: {expected_scr}")
    
    # CHECK
    if actual_start == expected_start and f"{expected_scr}" in status:
        print("\nSUCCESS: Headless E2E math validation passed for 15 items/scr!")
    else:
        print(f"\nFAILURE: Math mismatch! Expected {expected_start}, Got {actual_start}")
        sys.exit(1)
        
    app.quit()

if __name__ == "__main__":
    loop = QEventLoop(QApplication(sys.argv))
    asyncio.set_event_loop(loop)
    with loop:
        loop.run_until_complete(test_viewport_sequence())
