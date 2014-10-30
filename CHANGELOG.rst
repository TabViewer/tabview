*Version 1.0.1  2014-08-16*

 - Added '0' key for beginning of line. Updated modifier key handling.

*Version 1.1.0  2014-10-29*

 - Fixed #7 (extra highlighting when at bottom right cell)
 - Cleaned up header row toggling. Fixes #18
 - Added ability to reload file in-place. Fixes #2.
 - Added yank-to-clipboard. Fixes #13
 - Read entire file before deciding the encoding. Add some other encoding types to try before failing
 - Fixed #16 crash along with display of cells with newlines
