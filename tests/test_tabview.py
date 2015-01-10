#!/usr/bin/env python
# -*- coding: utf-8 -*-

import tabview.tabview as t

def test_tabview_file():
    r = t.view(fn='sample/data_ohlcv.csv', loop=False)
    assert(r is None) # maybe view should return something else

def test_tabview_data():
    a = [["a","b","c"], ["d","e","f"]]
    r = t.view(a, loop=False)
    assert(r is None)
