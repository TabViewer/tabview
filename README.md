[![Latest Version](https://img.shields.io/github/release/tabviewer/tabview.svg)](https://pypi.python.org/pypi/tabview/)
[![Supported Python versions](https://img.shields.io/pypi/pyversions/tabview.svg)](https://pypi.python.org/pypi/tabview/)
[![License](https://img.shields.io/pypi/l/tabview.svg)](https://pypi.python.org/pypi/tabview/)
[![Tests](https://github.com/TabViewer/tabview/actions/workflows/main.yml/badge.svg)](https://github.com/TabViewer/tabview/actions/workflows/main.yml)
[![Sourcegraph](https://sourcegraph.com/github.com/TabViewer/tabview/-/badge.svg)](https://sourcegraph.com/github.com/Tabviewer/tabview)

# Tabview

**This project is functional but future development will be sporadic and
limited. For a more fully featured CSV viewer/spreadsheet app check out the
[Visidata project](https://github.com/saulpw/visidata).**

View a CSV file in a spreadsheet-like display.

Posted by Scott Hansen <tech@firecat53.net>

> Original code forked from: http://www.amk.ca/files/simple/tabview.txt
>
> Contributed by A.M. Kuchling <amk@amk.ca>

Other Contributors:

- Matus Gura <matus.gura@gmail.com>
- Nathan Typanski <ntypanski@gmail.com>
- Sébastien Celles <s.celles@gmail.com>
- Yuri D'Elia <wavexx@thregr.org>

The highlighted position is shown in the top-left corner of the screen; next to
it are shown the contents of that cell.

## Features

- Python 3.11+
- Spreadsheet-like view for easily visualizing tabular data
- Vim-like navigation (h,j,k,l, g(top), G(bottom), 12G goto line 12, m - mark,
  ' - goto mark, etc.)
- Toggle persistent header row
- Sort ascending or descending by any column. Dynamically change column width
  and gap
- Sort in 'natural order' to improve numeric sorting
- Full-text incremental search, n and p to cycle between search results
- 'Enter' to view the full cell contents
- Yank cell contents to the clipboard
- File can be reloaded in-place if the data changes.
- F1 or ? for keybindings
- Can also use from python command line to visualize any tabular data (e.g.
  list-of-lists)
- See the screenshots directory for some pictures.

## Requires

- Python 3.11+
- wl-copy (Wayland), xclip or xsel (X11), or pbcopy (macOS) (Optional - only
  required for 'yank' to clipboard)

## Installation

- `pipx install tabview` OR
- `pip install tabview` OR
- `pip install .` (from a source checkout) OR
- [Archlinux AUR package](https://aur.archlinux.org/packages/tabview-git/)

## Usage

- From command line:

  ```sh
  tabview <filename>
  tabview <filename> --start_pos 6,5
  tabview <filename> +6:5  # equivalent to previous usage
  tabview <filename> --encoding iso8859-1 +6:
  ```

- From python command line to view an object:

  ```python
  import tabview as t
  a = [["a","b","c"], ["d","e","f"]]
  t.view(a)
  ```

- From python command line to view a file:

  ```python
  import tabview as t
  t.view(<filename>, start_pos=(60,40))
  ```

- Using as the pager for MySQL. Set these options in `~/.my.cnf`:

  ```ini
  pager=tabview -d '\t' --quoting QUOTE_NONE -
  silent
  ```

## Tests

- `make test` (creates a `.venv`), or `python -m unittest discover`.
  The integration tests need a terminal.

## Keybindings

```
F1 or ?                   Show this list of keybindings
Cursor keys or h,j,k,l    Move the highlighted cell, scrolling if required.
Q or q                    Quit
Home, ^, Ctrl-a           Move to the start of this line
End, $, Ctrl-e            Move to the end of this line
[num]|                    Goto column <num>, or first column
                          if num not given
PgUp/PgDn or J/K          Move a page up or down
H,L                       Page left or right
g                         Goto top of current column
[num]G                    Goto line <num> or bottom of current column
                          if num not given
Ctrl-g                    Show file/data information
Insert or m               Memorize this position
Delete or '               Return to memorized position (if any)
Enter                     View full cell contents in pop-up window.
/                         Search
n                         Next search result
p                         Previous search result
t                         Toggle fixed header row
< >                       Decrease/Increase column width (all columns)
, .                       Decrease/Increase column width (current column)
- +                       Decrease/Increase column gap
s                         Sort the table by the current column (ascending)
S                         Sort the table by the current column (descending)
a                         'Natural Sort' the table (ascending)
A                         'Natural Sort' the table (descending)
#                         Sort numerically by the current column (ascending)
@                         Sort numerically by the current column (descending)
r                         Reload file/data. Also resets sort order
y                         Yank cell contents to the clipboard
                          (requires wl-copy, xclip, xsel or pbcopy)
[num]c                    Toggle variable column width mode (mode/max),
                          or set width to [num]
[num]C                    Maximize current column, or set width to [num]
[num][                    Skip to (nth) change in row value (backward)
[num]]                    Skip to (nth) change in row value (forward)
[num]{                    Skip to (nth) change in column value (backward)
[num]}                    Skip to (nth) change in column value (forward)
```
