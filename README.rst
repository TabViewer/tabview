.. image:: https://pypip.in/version/tabview/badge.svg
    :target: https://pypi.python.org/pypi/tabview/
    :alt: Latest Version

.. image:: https://pypip.in/py_versions/tabview/badge.svg
    :target: https://pypi.python.org/pypi/tabview/
    :alt: Supported Python versions

.. image:: https://pypip.in/format/tabview/badge.svg
    :target: https://pypi.python.org/pypi/tabview/
    :alt: Download format

.. image:: https://pypip.in/license/tabview/badge.svg
    :target: https://pypi.python.org/pypi/tabview/
    :alt: License

.. image:: https://sourcegraph.com/api/repos/github.com/firecat53/tabview/.badges/status.png
   :target: https://sourcegraph.com/github.com/firecat53/tabview

.. image:: https://travis-ci.org/firecat53/tabview.svg?branch=master
    :target: https://travis-ci.org/firecat53/tabview

Tabview  
=========

View a CSV file in a spreadsheet-like display.

Posted by Scott Hansen <firecat4153@gmail.com>

    Original code forked from: http://www.amk.ca/files/simple/tabview.txt

    Contributed by A.M. Kuchling <amk@amk.ca>

Other Contributors:

    + Matus Gura <matus.gura@gmail.com>
    + Nathan Typanski <ntypanski@gmail.com>
    + Sébastien Celles <s.celles@gmail.com>
    + Yuri D'Elia <wavexx@thregr.org>

The highlighted position is shown in the top-left corner of the screen; next to
it are shown the contents of that cell.

Features:
---------
* Python 2.7+ and 3.x
* Spreadsheet-like view for easily visualizing tabular data
* Vim-like navigation (h,j,k,l, g(top), G(bottom), 12G goto line 12, m - mark,
  ' - goto mark, etc.) 
* Toggle persistent header row
* Sort ascending or descending by any column. Dynamically change column width and gap
* Sort in 'natural order' to improve numeric sorting
* Full-text incremental search, n and p to cycle between search results
* 'Enter' to view the full cell contents
* Yank cell contents to the clipboard
* File can be reloaded in-place if the data changes.
* F1 or ? for keybindings
* Can also use from python command line to visualize any tabular data (e.g.
  list-of-lists)
* See the screenshots directory for some pictures.

Requires: 
---------

* Python 2.7+ or 3.x
* Xsel or xclip (Optional - only required for 'yank' to clipboard)

Installation:
-------------

* ``pip install tabview`` OR
* ``# python setup.py install``  OR
* ``$ python setup.py install --user``  OR
* `Archlinux AUR package <https://aur.archlinux.org/packages/tabview-git/>`_

Usage:
------

* From command line:

  .. code:: python

    tabview <filename>
    tabview <filename> --start_pos 6,5
    tabview <filename> +6:5  (equivalent to previous usage)
    tabview <filename> --encoding iso8859-1 +6:

* From python command line to view an object

    .. code:: python
    
        import tabview as t
        a = [["a","b","c"], ["d","e","f"]]
        t.view(a)

* From python command line to view a file

    .. code:: python
    
        import tabview as t
        t.view(<filename>, start_pos=(60,40))

Tests:
------

* ``python tests/test_tabview.py``

Keybindings:
---------------

==========================   =================================================
**F1 or ?**                  Show this list of keybindings
**Cursor keys or h,j,k,l**   Move the highlighted cell, scrolling if required.
**Q or q**                   Quit
**Home, 0, ^, Ctrl-a**       Move to the start of this line
**End, $, Ctrl-e**           Move to the end of this line
**[num]|**                   Goto column <num>, or first column
                             if num not given
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
**< >**                      Decrease/Increase column width (all columns)
**, .**                      Decrease/Increase column width (current column)
**- +**                      Decrease/Increase column gap
**s**                        Sort the table by the current column (ascending)
**S**                        Sort the table by the current column (descending)
**a**                        'Natural Sort' the table (ascending)
**A**                        'Natural Sort' the table (descending)
**r**                        Reload file/data. Also resets sort order
**y**                        Yank cell contents to the clipboard
                             (requires xsel or xclip)
**[num]c**                   Toggle variable column width mode (mode/max),
                             or set width to [num]
**[num]C**                   Maximize current column, or set width to [num]
**[num][**                   Skip to (nth) change in row value (backward)
**[num]]**                   Skip to (nth) change in row value (forward)
**[num]{**                   Skip to (nth) change in column value (backward)
**[num]}**                   Skip to (nth) change in column value (forward)
==========================   =================================================
