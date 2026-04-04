import urllib.parse
import re
from typing import List, Optional, Dict, Any
from models.opds import OPDSFeed, Publication, Link, Group
from models.feed_page import FeedPage, FeedSection, FeedItem, ItemType, SectionLayout
from logger import get_logger

logger = get_logger("api.feed_reconciler")

# Threshold for choosing GRID layout over RIBBON for results sets
# MOVED TO UI LAYER

class FeedReconciler:
    """
    Transforms raw OPDS feeds into a unified structure.
    """
    
    @staticmethod
    def reconcile(feed: OPDSFeed, base_url: str) -> FeedPage:
        # Fallback title logic: metadata.title -> top-level title -> "Feed"
        page_title = "Feed"
        if feed.metadata and feed.metadata.title:
            page_title = feed.metadata.title
        elif hasattr(feed, 'title') and getattr(feed, 'title'):
            page_title = getattr(feed, 'title')
            
        sections = []
        facets = []
        
        # Robust logical ID and self/start detection
        self_url = base_url
        start_url = None
        if feed.links:
            for l in feed.links:
                rels = [l.rel] if isinstance(l.rel, str) else (l.rel or [])
                if "self" in rels:
                    self_url = urllib.parse.urljoin(base_url, l.href)
                if "start" in rels:
                    start_url = urllib.parse.urljoin(base_url, l.href)
        
        # Dashboard Heuristic: If start link refers to itself (or base_url), it's a dashboard
        is_dashboard = False
        if start_url:
            # Normalize for comparison
            s_norm = start_url.rstrip('/')
            self_norm = self_url.rstrip('/')
            if s_norm == self_norm:
                is_dashboard = True
                logger.debug(f"FeedReconciler: Dashboard detected via self-referencing 'start' link: {s_norm}")

        # Sanitize to create a stable ID for the entire logical feed.
        # Example: /codex/opds/v2.0/p/0/1 -> /codex/opds/v2.0/p/
        logical_id = re.sub(r'/[a-z]/\d+/\d+', lambda m: m.group(0)[:3], self_url).split('?')[0]
        
        logger.debug(f"FeedReconciler: base_url={base_url} -> logical_id={logical_id}")

        has_top_start = any(l.rel == "start" for l in feed.links) if feed.links else False
        
        # 0. Extract Facets
        if hasattr(feed, 'facets') and feed.facets:
            facets.extend(feed.facets)
        if feed.groups:
            for group in feed.groups:
                if getattr(group, "navigation", None):
                    has_facet = False
                    for n in group.navigation:
                        rel_str = "".join(n.rel or []) if isinstance(n.rel, list) else (n.rel or "")
                        if "facet" in rel_str or "http://opds-spec.org/facet" in rel_str:
                            has_facet = True
                            break
                    if has_facet:
                        facets.append(group)

        # 1. Handle Top-level Navigation
        if feed.navigation:
            nav_items = []
            for link in feed.navigation:
                rel_str = "".join(link.rel or []) if isinstance(link.rel, list) else (link.rel or "")
                if "start" in rel_str or (link.title and link.title.lower() == "start"):
                    continue
                nav_items.append(FeedItem(
                    type=ItemType.FOLDER,
                    title=link.title or "Untitled",
                    raw_link=link,
                    identifier=link.href
                ))
            
            if nav_items:
                m = feed.metadata
                sec_id = (m.identifier if m else None) or f"nav_{logical_id}"
                
                # It's a pure folder list, inherit global counts
                total = (m.numberOfItems if m else None) or len(nav_items)
                next_url = FeedReconciler._find_next(feed.links, base_url)
                
                sections.append(FeedSection(
                    title="Subsections",
                    section_id=sec_id,
                    items=nav_items,
                    total_items=total,
                    items_per_page=m.itemsPerPage if m else None,
                    current_page=(m.currentPage if m else None) or 1,
                    next_url=next_url
                ))

        # 2. Handle Groups
        if feed.groups:
            for group in feed.groups:
                group_items = []
                if group.publications:
                    for pub in group.publications:
                        group_items.append(FeedReconciler._pub_to_item(pub, base_url))
                
                if group.navigation:
                    for link in group.navigation:
                        rel_str = "".join(link.rel or []) if isinstance(link.rel, list) else (link.rel or "")
                        if "facet" in rel_str or "http://opds-spec.org/facet" in rel_str: continue
                        if has_top_start and ("start" in rel_str): continue
                            
                        group_items.append(FeedItem(
                            type=ItemType.FOLDER,
                            title=link.title or "Untitled",
                            raw_link=link,
                            identifier=link.href
                        ))
                
                if group_items:
                    gm = group.metadata
                    g_total = (gm.numberOfItems if gm else None) or len(group_items)
                    
                    # Look for self link in group links
                    g_self = None
                    if group.links:
                        for l in group.links:
                            rels = [l.rel] if isinstance(l.rel, str) else (l.rel or [])
                            if "self" in rels:
                                g_self = urllib.parse.urljoin(base_url, l.href)
                                break
                    
                    g_next = FeedReconciler._find_next(group.links, base_url)
                    
                    sections.append(FeedSection(
                        title=(gm.title if gm else None) or "Group",
                        section_id=(gm.identifier if gm else None) or f"group_{(gm.title if gm else 'anon')}",
                        items=group_items,
                        total_items=g_total,
                        items_per_page=gm.itemsPerPage if gm else None,
                        current_page=(gm.currentPage if gm else None) or 1,
                        next_url=g_next,
                        self_url=g_self
                    ))

        # 3. Handle Top-level Publications
        if feed.publications:
            pub_items = []
            for pub in feed.publications:
                pub_items.append(FeedReconciler._pub_to_item(pub, base_url))
            
            if pub_items:
                m = feed.metadata
                sec_id = (m.identifier if m else None) or f"pubs_{logical_id}"
                next_url = FeedReconciler._find_next(feed.links, base_url)
                
                sections.append(FeedSection(
                    title="Items",
                    section_id=sec_id,
                    items=pub_items,
                    total_items=m.numberOfItems if m else None,
                    items_per_page=m.itemsPerPage if m else None,
                    current_page=(m.currentPage if m else None) or 1,
                    next_url=next_url
                ))

        # 4. Data Cleaning / Optimization
        # Prune redundant server-side nesting (e.g. Codex grouping items that duplicate section titles)
        for section in sections:
            if len(section.items) > 1:
                first = section.items[0]
                # If the first item is a folder/header and matches the section title, it's redundant
                if first.type in (ItemType.FOLDER, ItemType.FOLDER): # Using ItemType.FOLDER as proxy for grouping
                    clean_first = re.sub(r'[^a-z0-9]', '', first.title.lower())
                    clean_sec = re.sub(r'[^a-z0-9]', '', section.title.lower())
                    if clean_first == clean_sec:
                        logger.info(f"FeedReconciler: Pruned redundant grouping item '{first.title}' in section '{section.title}'")
                        section.items.pop(0)
                        if section.total_items: section.total_items -= 1

        # 4. Determine Global Page
        m = feed.metadata
        curr_page = (m.currentPage if m else None) or 1
        if curr_page == 1 and base_url:
            # Fallback: Parse from URL if metadata is missing or stuck at 1
            parsed = urllib.parse.urlparse(base_url)
            path_parts = parsed.path.rstrip('/').split('/')
            # e.g. /opds/v2.0/p/0/1
            if len(path_parts) >= 3:
                prefix, group_id, page_num = path_parts[-3], path_parts[-2], path_parts[-1]
                if len(prefix) == 1 and page_num.isdigit() and group_id.isdigit():
                    curr_page = int(page_num)
            
            if curr_page == 1:
                # Try query params
                params = urllib.parse.parse_qs(parsed.query)
                if 'page' in params:
                    curr_page = int(params['page'][0])
                elif 'offset' in params:
                    offset = int(params['offset'][0])
                    limit = int(params.get('limit', [100])[0]) # Use a default limit if missing
                    curr_page = (offset // limit) + 1

        # 5. Determine Total Pages
        total_pages = None
        if m and m.numberOfItems and m.itemsPerPage:
            import math
            total_pages = math.ceil(m.numberOfItems / m.itemsPerPage)

        return FeedPage(
            title=page_title,
            current_page=curr_page,
            total_pages=total_pages,
            sections=sections,
            facets=facets,
            is_dashboard=is_dashboard
        )

    @staticmethod
    def _pub_to_item(pub: Publication, base_url: str) -> FeedItem:
        cover_url = None
        if pub.images:
            cover_url = urllib.parse.urljoin(base_url, pub.images[0].href)
        return FeedItem(
            type=ItemType.BOOK,
            title=pub.metadata.title,
            cover_url=cover_url,
            raw_pub=pub,
            identifier=pub.identifier
        )

    @staticmethod
    def _find_acquisition_link(pub: Publication, base_url: str = "") -> Optional[str]:
        """Helper to find an acquisition link in a publication or its manifest."""
        for l in (pub.links or []):
            # Normalize rels to a list of lower-case strings
            rels = l.rel
            if isinstance(rels, str):
                rel_list = [rels.lower()]
            elif isinstance(rels, list):
                rel_list = [str(r).lower() for r in rels]
            else:
                rel_list = []
                
            # Aggressive check for acquisition rels
            is_acq = any("acquisition" in r for r in rel_list)
            
            # Type-based detection (CBZ, CBR, PDF, EPUB, etc.)
            l_type = (l.type or "").lower()
            l_href = (l.href or "").lower()
            is_comic = any(t in l_type for t in ["cbz", "cbr", "cb7", "pdf", "octet-stream"]) or \
                       any(l_href.endswith(ext) for ext in [".cbz", ".cbr", ".cb7", ".pdf"])
            
            # If it's explicitly an acquisition link, or looks like a comic file, take it
            if is_acq or is_comic:
                # Avoid links that are clearly not downloads (like search, self, etc. if mislabeled)
                if any(r in rel_list for r in ["self", "search", "alternate"]) and not is_acq:
                    continue
                return urllib.parse.urljoin(base_url, l.href)
        return None

    @staticmethod
    def _find_next(links: List[Link], base_url: str) -> Optional[str]:
        if not links: return None
        for l in links:
            rel = l.rel if isinstance(l.rel, list) else [l.rel]
            if "next" in rel:
                return urllib.parse.urljoin(base_url, l.href)
        return None
