#!/usr/bin/env python

from distutils.core import setup

setup(
        name = "tabview",
        version = "1.0",
        description = "A curses command-line CSV and list (tabular data) viewer",
        long_description = open('README.txt').read(),
        author = "Scott Hansen",
        author_email = "firecat4153@gmail.com",
        url = "https://github.com/firecat53/tabview",
        packages = ['tabview'],
        scripts = ['bin/tabview'],
        package_data = {'tabview': ['README.txt']},
        data_files = [('share/doc/tabview',
                       ['README.txt', 'LICENSE.txt'])],
        license = "MIT",
)
