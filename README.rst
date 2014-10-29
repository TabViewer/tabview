Tabview  
=========

View a CSV file in a spreadsheet-like display.

Posted by Scott Hansen <firecat4153@gmail.com>

Original code forked from:
http://www.amk.ca/files/simple/tabview.txt
Contributed by A.M. Kuchling <amk@amk.ca>

The highlighted position is shown in the top-left corner of the screen; next to
it are shown the contents of that cell.

Features:
---------
* Python 3.x
* Spreadsheet-like view for easily visualizing tabular data
* Vim-like navigation (h,j,k,l, g(top), G(bottom), 12G goto line 12, m - mark,
  ' - goto mark, etc.) 
* Toggle persistent header row
* Sort ascending or descending by any column
* Full-text search, n and p to cycle between search results
* 'Enter' to view the full cell contents
* Yank cell contents to the clipboard
* File can be reloaded in-place if the data changes.
* F1 or ? for keybindings
* Can also use from python command line to visualize any tabular data (e.g.
  list-of-lists)
* See the screenshots directory for some pictures.

Requires: 
---------

* Python 3+
* Xsel or xclip (Optional - only required for 'yank' to clipboard)

Installation:
-------------

* ``# python setup.py install``  OR
* ``$ python setup.py install --user``  OR
* `Archlinux AUR package <https://aur.archlinux.org/packages/tabview-git/>`_

Usage:
------

* From command line:  ``tabview <filename>``
* From python command line to view an object::

        import tabview.tabview as t
        a = [["a","b","c"], ["d","e","f"]]
        t.view(a)

* From python command line to view a file::

        import tabview.tabview as t
        t.view(fn=<filename>)

Keybindings:
---------------

==========================   =================================================
**F1 or ?**                  Show this list of keybindings
**Cursor keys or h,j,k,l**   Move the highlighted cell, scrolling if required.
**Q or q**                   Quit
**Home, 0 or ^**                Move to the start of this line
**End or $**                 Move to the end of this line
**PgUp/PgDn or J/K**         Move a page up or down
**H,L**                      Page left or right
**g**                        Goto top of current column
**[num]G**                   Goto line <num> or bottom of current column 
                             if num not given
**Insert or m**              Memorize this position
**Delete or '**              Return to memorized position (if any)
**Enter**                    View full cell contents in pop-up window.
**/**                        Search
**n**                        Next search result
**p**                        Previous search result
**t**                        Toggle fixed header row
**s**                        Sort the table by the current column (ascending)
**S**                        Sort the table by the current column (descending)
**r**                        Reload file/data. Also resets sort order
**y**                        Yank cell contents to the clipboard
                             (requires xsel or xclip)
==========================   =================================================
