#!/usr/bin/env python

from distutils.core import setup
try:
    # Setuptools only needed for building the package
    import setuptools
except ImportError:
    pass

setup(name="tabview",
      version="1.4.0",
      description="A curses command-line CSV and list (tabular data) viewer",
      long_description=open('README.rst').read(),
      author="Scott Hansen",
      author_email="firecat4153@gmail.com",
      url="https://github.com/firecat53/tabview",
      download_url="https://github.com/firecat53/tabview/tarball/1.4.0",
      packages=['tabview'],
      scripts=['bin/tabview'],
      package_data={'tabview': ['README.rst']},
      data_files=[('share/doc/tabview',
                   ['README.rst', 'LICENSE.txt', 'CHANGELOG.rst'])],
      license="MIT",
      classifiers=[
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Environment :: Console :: Curses',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.2',
          'Programming Language :: Python :: 3.3',
          'Programming Language :: Python :: 3.4',
          'Topic :: Scientific/Engineering',
          'Topic :: Office/Business :: Financial :: Spreadsheet',
          'Topic :: Scientific/Engineering :: Visualization',
          'Topic :: Utilities',
      ],
      keywords='data spreadsheet view viewer console curses csv comma separated values',

      )
