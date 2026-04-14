# ComicCatcher TODO

## Auth
    For Komga, need to support different auth header from stump or codex
        X-API-Key: your_generated_key_here
     Update config dialog to be more clear about exclusive uname/pass, or key, or nothing
     Support the OPDS v1 Auth method  - do we persist user/pass? Or is there a cookie or something?



THis shouldn't be happening on a manifest pages?  
2026-04-14 14:09:07,734 - comiccatcher.api.feed_reconciler - WARNING - FeedReconciler: Discarding discrepant root pagination metadata. itemsPerPage=20 but no section contains exactly 20 items (found sections with counts: [1]).


changing library folder doesn't work

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

* Stump -
  * full-size thumbnails
  * pub date format in feed not standard
  * progression not working
  * Latest Books / Keep Reading preview groups on start feed aren't getting updated even though the linked feeds are up-to-date
  * Same problem for <library-name>/Library Books - Latest preview group
  

## Misc Lower
  
* refactoring opportunities:
  * check for any buttons, margins, sizes, font sizes, etc that aren't scaled
  * centralize all style setting, and have everything respect themes
  * more consolidation/deduplcation of code
  * less magic numbers every. Too man literal constants.
  * maybe more  `QFontMetrics`etc to calculate offsets proportional to font size.
  * better text eliding via QTextLayout, maybe, if not a performace hit

*  readino space opera incorrectly decided as infinite sections and NOT infinite grid. App needs more robust "main section" selection. It may not be possible to be perfect

* bug with scrolled feeds or codex giving wrong series count.
    manifests as extra cards at end of seroes scroll in codex (think codex is culprit when counts aren't updated when files are removed/added)

* add series/position (if available) to mini details

## Future Enhancments
* OPDS 1.2 
* Search/filter in library
* Handle OPDS Auth with special GUI
* Different sized cards: small/medium/large

