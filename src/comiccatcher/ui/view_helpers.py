import asyncio
from typing import Set, Tuple, Optional, Callable
from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QListView
from comiccatcher.models.feed_page import FeedItem

class ViewportHelper:
    """
    Shared utilities for viewport visibility detection and resource fetching.
    Consolidates logic used by FeedBrowser, FeedDetailView, and others.
    """

    @staticmethod
    def get_visible_range(view: QListView, buffer: int = 0) -> Tuple[int, int]:
        """
        Calculates the range of visible row indices (first, last) in a QListView.
        Robust against margins and gutters by using small corner offsets.
        """
        if not view or not view.isVisible():
            return 0, -1
            
        vp = view.viewport()
        if not vp:
            return 0, -1
            
        rect = vp.rect()
        # Use 10px offsets to ensure we hit the actual card content
        first_idx = view.indexAt(rect.topLeft() + QPoint(10, 10))
        last_idx = view.indexAt(rect.bottomRight() - QPoint(10, 10))
        
        model = view.model()
        row_count = model.rowCount() if model else 0
        
        if row_count == 0:
            return 0, -1

        first = first_idx.row() if first_idx.isValid() else 0
        
        if last_idx.isValid():
            last = last_idx.row()
        else:
            # Fallback: If bottomRight didn't hit an item, use a safe estimate
            # based on current view mode.
            if view.viewMode() == QListView.ViewMode.IconMode:
                # Conservative estimate for grids/ribbons
                last = min(row_count - 1, first + 30)
            else:
                last = min(row_count - 1, first + 15)
            
        if buffer > 0:
            first = max(0, first - buffer)
            last = min(row_count - 1, last + buffer)
            
        return first, last

    @staticmethod
    async def fetch_cover_async(
        url: str, 
        image_manager, 
        pending_set: Set[str], 
        on_done_callback: Optional[Callable] = None,
        max_dim: int = 400,
        timeout: Optional[float] = None
    ):
        """
        Asynchronously fetches a cover thumbnail via ImageManager.
        Manages a 'pending_set' to prevent redundant concurrent requests.
        """
        if not url or url in pending_set:
            return
            
        pending_set.add(url)
        try:
            await image_manager.get_image_b64(url, max_dim=max_dim, timeout=timeout)
        except Exception:
            # Failures are logged by ImageManager
            pass
        finally:
            pending_set.discard(url)
            
        if on_done_callback:
            on_done_callback()
