#!/usr/bin/env python

from distutils.core import setup

setup(
    name='Mrj3',
    version='0.2.3',
    description='Control your MR-J3 over a serial port',
    author='John Brodie',
    author_email='john@brodie.me',
    url='http://www.github.com/JohnBrodie/pyjector',
    packages=['mrj3'],
    install_requires=[
        'pyserial',
    ],
    package_data={
        'mrj3': ['mrj3_configs/*.json'],
    },
)
