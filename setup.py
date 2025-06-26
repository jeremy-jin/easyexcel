#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
    name="easyexcel",
    version="0.0.1",
    description="A simple library for parsing Excel files",
    packages=find_packages("src"),
    package_dir={"": "src"},
    install_requires=[
        "openpyxl==3.1.5",
        "python-dateutil==2.9.0.post0",
    ],
    extras_require={
        "dev": [
            "pytest==6.2.5",
            "flake8==3.9.2",
            "black==22.3.0",
            "coverage==5.5",
            "python-dateutil==2.9.0.post0",
        ],
    },
    zip_safe=True,
    entry_points={
        "console_scripts": [

        ]
    },
)
