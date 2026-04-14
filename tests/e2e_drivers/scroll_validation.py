import asyncio
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import QApplication
from comiccatcher.ui.theme_manager import UIConstants

async def drive(window):
    """
    E2E Driver: Verifies that the 'Down' arrow key scrolls exactly one row height.
    Logic: (Card Height + Gutter).
    """
    print("🚗 E2E Scroll Validation Started")
    await asyncio.sleep(5) # Wait for initial feed load
    
    browser = window.feed_browser
    show_labels = window.config_manager.get_show_labels()
    
    # Calculation matches base_feed_subview.py: _get_scroll_step
    expected_step = UIConstants.get_card_height(show_labels, reserve_progress_space=False) + UIConstants.GRID_GUTTER
    print(f"[*] Expected Row Step: {expected_step}px (Labels: {show_labels})")

    async def run_test():
        # Wait for LoadingOverlay to go away (up to 15s)
        view = None
        for _ in range(30):
            view = browser.stack.currentWidget()
            if type(view).__name__ not in ("LoadingOverlay", "ErrorOverlay"):
                break
            await asyncio.sleep(0.5)

        view_name = type(view).__name__
        print(f"\n[*] Active View: {view_name}")
        
        if view_name == "LoadingOverlay":
            print("⚠️ Still loading...")
            return False

        # Robust Scrollbar/Viewport discovery
        sb = None
        target = None
        if hasattr(view, "_impl"): # ScrolledFeedView (ScrollArea wrapper)
            sb = view._impl.verticalScrollBar()
            target = view._impl.viewport()
        elif hasattr(view, "scroll_area"): # PagedFeedView (ScrollArea wrapper)
            sb = view.scroll_area.verticalScrollBar()
            target = view.scroll_area.viewport()
        elif hasattr(view, "list_widget"): # LocalLibraryView
            sb = view.list_widget.verticalScrollBar()
            target = view.list_widget.viewport()
            
        if not sb or not target:
            print(f"❌ Failed to find scrollbar/viewport for {view_name}")
            return False

        if sb.maximum() == 0:
            print(f"⚠️ No scroll range (0-0). Feed might be small.")
            return False

        start = sb.value()
        print(f"    Initial Scroll: {start}")
        
        # Simulating the Key
        from PyQt6.QtCore import QCoreApplication
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Down, Qt.KeyboardModifier.NoModifier)
        
        # We send it to the widget itself (NOT its viewport or eventFilter).
        # This allows Qt's standard event propagation to happen.
        # Since the filter is now on the VIEW widget, we send it there.
        target_widget = view._impl if hasattr(view, "_impl") else (view.scroll_area if hasattr(view, "scroll_area") else (view.list_widget if hasattr(view, "list_widget") else view))
        
        print(f"    Sending [DOWN] to {type(target_widget).__name__}...")
        QCoreApplication.postEvent(target_widget, event)
        
        # Need to wait longer for postEvent to be processed by the loop
        await asyncio.sleep(1.0)
        delta = sb.value() - start
        print(f"    Actual Delta: {delta}px")
        
        if delta == expected_step:
            print(f"✅ SUCCESS: {view_name} scrolled exactly one row.")
        else:
            print(f"❌ FAILED: {view_name} delta {delta} != {expected_step}")
        return True

    # Test current view
    await run_test()

    # Toggle mode and test again
    print("\n[*] Toggling view mode...")
    current_view = browser.stack.currentWidget()
    if type(current_view).__name__ == "ScrolledFeedView":
        browser._on_paging_mode_changed("paged")
    else:
        browser._on_paging_mode_changed("scrolled")
        
    await asyncio.sleep(3)
    await run_test()

    print("\n🏁 E2E Validation Complete")
    await asyncio.sleep(1)
    QApplication.instance().quit()
