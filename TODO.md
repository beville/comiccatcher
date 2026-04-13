# ComicCatcher TODO

## Feed Stuff

* bug with scrolled feeds or codex giving wrong series count.
    manifests as extra cards at end of seroes scroll in codex (think codex is culprit when counts aren't updated when files are removed/added)

* handle pagination metadata that may be corrupt or buggy.  Might need an "unknown" concept for itemsperpage, and number of items if the first page data doesn't match those numbers
   See: https://www.lirtuel.be/v1/bundles.opds2

* Bad OPDS pages to maybe work around:
   komga > Latest Series See All, somehow goes to publications (also probably a bug report for komga)

## Reader & UI

*  readino space opera is infinite sections.

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
* Komga icon komgaandroid url is wrong
* Komga Latest Series See All, somehow goes to publications 
* Codex - feed start thinks it's a publisher list 

## Misc Lower

  
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
* Handle OPDS Auth with special GUI
* Different sized cards: small/medium/large
* Inifinite scroll for special cases
  * handle cases of: 
    * main group found but no last page - this may require reording to have nav section last (if it's the main group) 
      * readino publications lists need this
      * build on only the main group, but scroll bar keeps changing size)
    * no main group, but multi pages (like the litruel "Featured Selections" with no last page link, and many groups)
      * i guess just add each group after group as they appear in the pages. scroll bar keeps chaging size)
