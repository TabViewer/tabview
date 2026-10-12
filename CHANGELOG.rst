*Unreleased*

  - Require Python 3.11+; test against Python 3.11 through 3.15
  - Replace setup.py (distutils was removed in Python 3.12) with pyproject.toml
  - Install the ``tabview`` command as a console script entry point and add
    ``python -m tabview`` support
  - Replace Travis CI with GitHub Actions
  - Remove Python 2 compatibility shims
  - Use the locale encoding (not UTF-8 mode) as the first encoding guess
  - Yank: add wl-copy (Wayland) support, fix pbcopy on macOS (it was skipped
    when DISPLAY was unset) and stop at the first clipboard tool that works
  - Input fixes:

    - Sniff the delimiter from several lines and only consider real delimiter
      characters (single-column files were split on letters); fall back
      instead of crashing when sniffing fails
    - Handle UTF-8/UTF-16/UTF-32 byte order marks; try Windows-1252 before
      Latin-1
    - Handle CR-only line endings without an extra blank row
    - Space-delimited files: keep quoted fields together and don't crash on
      apostrophes
    - Filenames containing '#', '?' or ';' can be opened; file:// URIs are
      unquoted
    - Print a message instead of crashing (or exiting silently) on empty input
    - view() accepts path-like objects, text file objects and ragged tuples
    - ``--delimiter`` and ``--quote-char`` accept escapes like ``\t`` and
      ``\x01`` and must be a single character
  - Display fixes:

    - Show control characters (tabs, NUL, escape, ...) in cells as escapes
      instead of crashing
    - Column widths can no longer shrink to zero or below (``,``, ``0c``,
      ``0C``), which crashed the display
    - Show "Terminal too small" instead of crashing on tiny terminals
    - Fullwidth characters count as double width
    - LINES/COLUMNS environment variables no longer override the real
      terminal size on the first screen
    - Enter no longer opens a pop-up for empty cells
  - Natural sort no longer crashes on cells like '²'; numeric sort puts NaN
    after the other numbers instead of scrambling the order
  - CLI: clear error messages instead of tracebacks for bad start positions,
    unknown options or encodings, missing files and missing /dev/tty; partial
    start positions like ``+5:`` work
  - Ctrl-C exits with status 130
  - Fix ``--width`` help, which said the default was 'mode' (it is 20)

*Version 1.4.4 2020/01/09*

  - Remove Python 2.x support
  - Add note about Visidata and minimal maintenance
  - Add file URI scheme support
  - Fix flake8 errors
  - Remove python 3.3 support
  - Update travis.yml for newer python versions and fix flake8 command
  - Add sample text with long/wide characters

*Version 1.4.3 2017/11/13*

  - Added an additional parse step for space-delimited files:
    1. Replace multiple spaces (such as those to align columns) with a single
       space.
    2. If (and only if) the top line begins with a standard comment character
       ('#' or '%'), it is removed.
  - Remove '0' for BOL and change numeric sort to '#'/'@'
  - Add numeric sort
  - Provide ability to specify quotechar

*Version 1.4.2 2016/01/17*

 - Fix some packaging issues
 - Can now run 'python setup.py test' to run the unit tests

*Version 1.4.1 2015/04/04*

 - File/data information popup
 - Allow handling of different quoting schemes

*Version 1.4.0 2015/02/21*
 - Incremental (find-as-you type) search
 - Reload changed file, saving various display parameters
 - Variable width columns ('mode', 'max' or fixed width)
 - Support reading from stdin
 - Resize columns individually or as a whole
 - Add commands to skip to next changed value (by row column)
 - Pass a y,x start position on command line or to view()

*Version 1.3.0 2015-01-17*
 - Added basic unit and integration tests
 - Travis integration
 - Other speed improvements and bug fixes

*Version 1.2.0  2015-01-08*

 - Dual Python 2.7+ and 3+ support. Improved Unicode handling
 - 'Natural' sort capability for better numeric sorting
 - Added dynamic column width and gap adjustment and jump to column command
 - Handle terminal resizing
 - Numerous crash fixes

*Version 1.1.0  2014-10-29*

 - Fixed #7 (extra highlighting when at bottom right cell)
 - Cleaned up header row toggling. Fixes #18
 - Added ability to reload file in-place. Fixes #2.
 - Added yank-to-clipboard. Fixes #13
 - Read entire file before deciding the encoding. Add some other encoding types to try before failing
 - Fixed #16 crash along with display of cells with newlines

*Version 1.0.1  2014-08-16*

 - Added '0' key for beginning of line. Updated modifier key handling.
