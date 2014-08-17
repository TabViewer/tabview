#!/usr/bin/env python

from distutils.core import setup

setup(name="tabview",
      version="1.0.1",
      description="A curses command-line CSV and list (tabular data) viewer",
      long_description=open('README.rst').read(),
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/tabview",
      download_url="https://github.com/firecat53/tabview/tarball/1.0.1",
      packages=['tabview'],
      scripts=['bin/tabview'],
      package_data={'tabview': ['README.rst']},
      data_files=[('share/doc/tabview',
                   ['README.rst', 'LICENSE.txt', 'CHANGELOG.rst'])],
      license="MIT",
      )
