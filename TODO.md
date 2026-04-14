# ComicCatcher TODO

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

