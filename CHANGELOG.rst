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
