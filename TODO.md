# ComicCatcher TODO

* bug with scrolled feeds or codex giving wrong series count.
    manifests as extra cards at end of seroes scroll in codex (think codex is culprit when counts aren't updated when files are removed/added)

* handle pagination metadata that may be corrupt or buggy.  Might need an "unknown" concept for itemsperpage, and number of items if the first page data doesn't match those numbers
   See: https://www.lirtuel.be/v1/bundles.opds2

* Bad OPDS pages to maybe work around:
   komga > Latest Series See All, somehow goes to publications

* adjacentbook popover - use title (and maybe subtitle)
* details views - handle wide covers
* details views - use more metadata (web, genre...)
* details viw max width, maybe centered

* keystrokes for feed and library
* reader keystrokes and controls fixing

* scrolled view optimize page and thumb fetching

* add support for minimal epub 

* pypi account
* windows and mac testing

* reader UI re-evaluate

* fix  "komgaandroid" URL hack in `feed_management.py`.
* Duplicate Artist grouping, Date formatting, and File Size logic in `LocalDetailView`, `FeedDetailView`, and `MiniDetailPopover`.
* String-based color replacement in `ThemeManager` and `BaseCardDelegate` instead of CSS/proper SVG manipulation.
* more consolidation/deduplcation of code
* less magic numbers
* maybe more  `QFontMetrics` to calculate offsets proportional to font size.
* better text eliding via QTextLayout, maybe

## Future
* OPDS 1.2 
* Search/filter in library
