from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import IntEnum
from .opds import Publication, Link, Metadata

class ItemType(IntEnum):
    BOOK = 1
    FOLDER = 2 # Series, Subsection, etc.
    HEADER = 3 # Section Title
    EMPTY = 4  # Skeleton placeholder

class FeedItem(BaseModel):
    """A single visual card or header in the grid."""
    type: ItemType
    title: str
    subtitle: Optional[str] = None
    cover_url: Optional[str] = None
    
    # Original data for actions
    raw_pub: Optional[Publication] = None
    raw_link: Optional[Link] = None # For Folders
    
    # Identifier for deduplication and sparse matching
    identifier: str
    
    # For pagination: which page does this item belong to?
    page_index: Optional[int] = None

class SectionLayout(IntEnum):
    RIBBON = 1 # Horizontal
    GRID = 2   # Vertical (The "Main Event")

class FeedSection(BaseModel):
    """A logical grouping of items (e.g. 'Latest', 'All Series')."""
    title: str
    layout: SectionLayout = SectionLayout.RIBBON
    items: List[FeedItem] = []
    
    # Pagination metadata
    total_items: Optional[int] = None
    current_page: int = 1
    items_per_page: Optional[int] = None
    next_url: Optional[str] = None
    self_url: Optional[str] = None
    
    # Unique ID to reconcile across paginated responses
    section_id: str

class FeedPage(BaseModel):
    """The entire state of a feed view."""
    title: str
    current_page: int = 1
    total_pages: Optional[int] = None
    sections: List[FeedSection] = []
    facets: List[Any] = [] # List of Group objects or dicts for filters

    pagination_template: Optional[str] = None # {page}
    is_offset_based: bool = False
    is_dashboard: bool = False

    # Breadcrumbs for navigation

    breadcrumbs: List[Dict[str, str]] = [] # [{"title": "Home", "url": "..."}]

    @property
    def main_section(self) -> Optional[FeedSection]:
        """Identifies the primary content section based on size and layout."""
        if not self.sections:
            return None

        from ui.theme_manager import UIConstants
        
        # 1. Look for a section that is ALREADY large in this response
        # or is explicitly paginated (has a next link)
        for s in self.sections:
            # We focus on what we actually HAVE right now. 
            # If we only have 10 items, it's a ribbon regardless of total_items.
            if len(s.items) > UIConstants.LARGE_SECTION_THRESHOLD or s.next_url:
                return s

        # 2. Look for a section explicitly marked as GRID
        grids = [s for s in self.sections if s.layout == SectionLayout.GRID]
        if grids:
            return max(grids, key=lambda s: len(s.items))

        # 3. Fallback: If it's a dashboard, don't force a grid if the sections are just preview links.
        if self.is_dashboard:
            # Check the last section. If it has a way to see more (self_url), 
            # and it's currently small, keep it as a ribbon.
            last = self.sections[-1]
            if last.self_url and len(last.items) <= UIConstants.LARGE_SECTION_THRESHOLD:
                return None
            return last
            
        # For non-dashboards (single results lists), always use the last/only section
        return self.sections[-1]

