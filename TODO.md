# ComicCatcher TODO

## Feed Stuff

* bug with scrolled feeds or codex giving wrong series count.
    manifests as extra cards at end of seroes scroll in codex (think codex is culprit when counts aren't updated when files are removed/added)

* handle pagination metadata that may be corrupt or buggy.  Might need an "unknown" concept for itemsperpage, and number of items if the first page data doesn't match those numbers
   See: https://www.lirtuel.be/v1/bundles.opds2

* Bad OPDS pages to maybe work around:
   komga > Latest Series See All, somehow goes to publications (also probably a bug report for komga)

## Reader & UI

* keystrokes for feed and library

* reader keystrokes and controls fixing

## deployment

* set up github actions for
  * pypi package and deployment
  * appimage creation
  * standalone windows exe
  * unsigned macos app 

## testing

* windows and mac testing

## bug reports:

* Stump - not handling https links
* Komga icon komgaandroid name is weird
* Komga Latest Series See All, somehow goes to publications 
* Codex - feed start thinks it's a publisher list 

## Misc Lower

  
* fix  "komgaandroid" URL hack in `feed_management.py`. (might be a bug report for komga)
* refactoring opportunities:
  * check for any buttons, margins, sizes, font sizes, etc that aren't scaled
  * centralize all style setting, and have everything respect themes
  * more consolidation/deduplcation of code
  * less magic numbers every. Too man literal constants.
  * maybe more  `QFontMetrics`etc to calculate offsets proportional to font size.
  * better text eliding via QTextLayout, maybe, if not a performace hit

## Future Enhancments
* OPDS 1.2 
* Search/filter in library
* Inifinite scroll even if no main axis data found
* Handle OPDS Auth with special GUI
* Different sized cards: small/medium/large
